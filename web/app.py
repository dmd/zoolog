#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "flask>=3.0.0",
#     "markdown>=3.5.1",
#     "tqdm>=4.66.0",
# ]
# ///
"""
Zoolog Web Interface - Flask backend

Security Notes:
- All endpoints are GET/read-only, so CSRF protection is not required
- If POST/PUT/DELETE endpoints are added in the future, implement CSRF protection
"""
import atexit
import os
import sqlite3
import quopri
import re
import shlex
import shutil
import subprocess
import tempfile
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file
import markdown
from tqdm import tqdm

app = Flask(__name__)

# Configuration
DB_URI = "file:zoolog?mode=memory&cache=shared"
_PERSISTENT_CONN = None
POSTS_DIR = Path(__file__).parent.parent / 'posts'
PANDOC_CSS_PATH = Path(__file__).parent.parent / 'pandoc.css'
PHOTOS_DIR = Path(__file__).parent / 'photos'
SHORTCUT_NAME = "photosondate"

class PhotoFetchError(Exception):
    """Base exception for photo fetching issues."""

class PhotoFetchTimeout(PhotoFetchError):
    """Raised when the photo fetching process times out."""

def get_db():
    """Get database connection"""
    ensure_persistent_connection()
    conn = sqlite3.connect(DB_URI, uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_persistent_connection():
    """Ensure the shared in-memory database stays alive for the process lifetime"""
    global _PERSISTENT_CONN
    if _PERSISTENT_CONN is None:
        _PERSISTENT_CONN = sqlite3.connect(DB_URI, uri=True, check_same_thread=False)
        _PERSISTENT_CONN.row_factory = sqlite3.Row
    return _PERSISTENT_CONN

def cleanup_photos_dir():
    """Remove cached photos on shutdown so each run starts fresh."""
    try:
        if PHOTOS_DIR.exists():
            shutil.rmtree(PHOTOS_DIR)
    except Exception:
        pass

atexit.register(cleanup_photos_dir)

def fetch_photos_for_date(date_str, timeout=15):
    """Fetch photos for the given date using the Shortcuts app and resize them with ImageMagick."""
    PHOTOS_DIR.mkdir(exist_ok=True)
    destination_dir = PHOTOS_DIR / date_str
    destination_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        shortcuts_output = tmp_path / "out"

        try:
            result = subprocess.run(
                ["shortcuts", "run", SHORTCUT_NAME, "-i", date_str, "-o", str(shortcuts_output)],
                capture_output=True,
                text=True,
                timeout=timeout
            )
        except FileNotFoundError as exc:
            raise PhotoFetchError("The 'shortcuts' command is not available on this system.") from exc
        except subprocess.TimeoutExpired as exc:
            raise PhotoFetchTimeout("Timed out while running the Shortcuts automation.") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else "Unknown error from Shortcuts."
            raise PhotoFetchError(f"Shortcuts automation failed: {stderr}")

        if shortcuts_output.is_dir():
            candidates = [p for p in shortcuts_output.iterdir() if p.is_file()]
        elif shortcuts_output.exists():
            candidates = [shortcuts_output]
        else:
            candidates = []

        photos = [c for c in candidates if c.suffix.lower() != ".mov"]
        if not photos:
            return []

        converted_files = []
        for idx, src in enumerate(sorted(photos), start=1):
            dest = tmp_path / f"{date_str}-{idx}.jpg"
            try:
                convert = subprocess.run(
                    ["magick", str(src), "-resize", "1000x", str(dest)],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
            except FileNotFoundError as exc:
                raise PhotoFetchError("ImageMagick 'magick' command is required but was not found.") from exc
            except subprocess.TimeoutExpired as exc:
                raise PhotoFetchTimeout("Timed out while resizing photos with ImageMagick.") from exc

            if convert.returncode != 0:
                stderr = convert.stderr.strip() if convert.stderr else "Unknown ImageMagick error."
                raise PhotoFetchError(f"ImageMagick conversion failed: {stderr}")

            converted_files.append(dest)

        final_names = []
        for converted in sorted(converted_files):
            final_path = destination_dir / converted.name
            shutil.move(str(converted), final_path)
            final_names.append(final_path.name)

        return final_names

def clean_text_for_search(text):
    """Clean text for search indexing by removing punctuation and normalizing"""
    if not text:
        return ""

    # Remove punctuation and normalize whitespace
    cleaned = re.sub(r'[^\w\s]', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def extract_post_info(filename, content):
    """Extract metadata from post filename and content"""
    # Parse filename: YYYY-MM-DD-[category]-YYYY-MM-DD.txt
    parts = filename.replace('.txt', '').split('-')
    if len(parts) < 6:
        return None

    date_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
    try:
        post_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

    # Determine category
    category = "US"  # default
    if "AHNS" in filename:
        category = "AHNS"
    elif "J" in filename:
        category = "J"
    elif "-D-" in filename:
        category = "D"
    elif "-A-" in filename:
        category = "A"
    # Keep US as default for any other cases

    # First decode quoted-printable for processing
    try:
        decoded_content = quopri.decodestring(content.encode('utf-8')).decode('utf-8')
    except:
        decoded_content = content

    # Skip first line (date/category info) and create title from content
    lines = decoded_content.strip().split('\n')
    content_start_idx = 0

    if lines and lines[0].startswith('#'):
        content_start_idx = 1  # Skip the first line

    # Get content without first line (which is just date/category info)
    content_text = '\n'.join(lines[content_start_idx:]).strip() if len(lines) > content_start_idx else ""

    # Create title from first 50 chars of content, or use date if no content
    if content_text:
        title = content_text[:50].replace('\n', ' ').strip()
        if len(content_text) > 50:
            title += "..."
    else:
        title = f"{post_date.strftime('%Y-%m-%d')} {category}"

    # Create excerpt (first 200 chars) from content (excluding first line)
    excerpt = content_text[:200] + "..." if len(content_text) > 200 else content_text

    # Clean content for search indexing (remove punctuation)
    clean_content = clean_text_for_search(content_text)
    clean_title = clean_text_for_search(title)

    return {
        'filename': filename,
        'date': post_date,
        'category': category,
        'title': title,
        'content': content_text,
        'clean_content': clean_content,
        'clean_title': clean_title,
        'excerpt': excerpt,
        'year': post_date.year,
        'month': post_date.month,
        'day': post_date.day
    }

def create_database(conn):
    """Create the posts database with FTS support"""
    cursor = conn.cursor()

    # Main posts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT,
            content TEXT,
            clean_title TEXT,
            clean_content TEXT,
            excerpt TEXT,
            year INTEGER,
            month INTEGER,
            day INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add missing columns if they don't exist
    try:
        cursor.execute('ALTER TABLE posts ADD COLUMN clean_title TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cursor.execute('ALTER TABLE posts ADD COLUMN clean_content TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Full-text search virtual table using cleaned content
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
            filename, clean_title, clean_content, category,
            content='posts',
            content_rowid='id'
        )
    ''')

    # Triggers to keep FTS in sync
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN
            INSERT INTO posts_fts(rowid, filename, clean_title, clean_content, category)
            VALUES (new.id, new.filename, new.clean_title, new.clean_content, new.category);
        END
    ''')

    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS posts_ad AFTER DELETE ON posts BEGIN
            INSERT INTO posts_fts(posts_fts, rowid, filename, clean_title, clean_content, category)
            VALUES('delete', old.id, old.filename, old.clean_title, old.clean_content, old.category);
        END
    ''')

    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS posts_au AFTER UPDATE ON posts BEGIN
            INSERT INTO posts_fts(posts_fts, rowid, filename, clean_title, clean_content, category)
            VALUES('delete', old.id, old.filename, old.clean_title, old.clean_content, old.category);
            INSERT INTO posts_fts(rowid, filename, clean_title, clean_content, category)
            VALUES (new.id, new.filename, new.clean_title, new.clean_content, new.category);
        END
    ''')

    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_date ON posts(date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_year_month ON posts(year, month)')

    conn.commit()

def index_posts():
    """Index all posts in the posts directory"""
    if not POSTS_DIR.exists():
        print(f"Posts directory not found: {POSTS_DIR}")
        return False
    
    conn = ensure_persistent_connection()
    create_database(conn)
    cursor = conn.cursor()

    # Clear existing data
    cursor.execute('DELETE FROM posts')
    conn.commit()

    indexed_count = 0
    error_count = 0

    # Get list of files for progress bar
    txt_files = list(POSTS_DIR.glob('*.txt'))

    for txt_file in tqdm(txt_files, desc="Indexing posts", unit="post"):
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()

            post_info = extract_post_info(txt_file.name, content)
            if post_info:
                cursor.execute('''
                    INSERT INTO posts (filename, date, category, title, content, clean_title, clean_content, excerpt, year, month, day)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    post_info['filename'],
                    post_info['date'].isoformat(),
                    post_info['category'],
                    post_info['title'],
                    post_info['content'],
                    post_info['clean_title'],
                    post_info['clean_content'],
                    post_info['excerpt'],
                    post_info['year'],
                    post_info['month'],
                    post_info['day']
                ))
                indexed_count += 1

                if indexed_count % 1000 == 0:
                    conn.commit()
            else:
                error_count += 1

        except Exception as e:
            tqdm.write(f"Error processing {txt_file.name}: {e}")
            error_count += 1

    conn.commit()

    # Get stats
    cursor.execute('SELECT COUNT(*) FROM posts')
    total_posts = cursor.fetchone()[0]

    cursor.execute('SELECT MIN(date), MAX(date) FROM posts')
    date_range = cursor.fetchone()

    cursor.execute('SELECT category, COUNT(*) FROM posts GROUP BY category ORDER BY category')
    category_stats = cursor.fetchall()

    print(f"\nIndexing complete!")
    print(f"Total posts indexed: {total_posts}")
    print(f"Errors: {error_count}")
    if date_range and date_range[0]:
        print(f"Date range: {date_range[0]} to {date_range[1]}")
        print(f"Categories:")
        for cat, count in category_stats:
            print(f"  {cat}: {count} posts")

    return True

def sanitize_fts_query(query):
    """Sanitize FTS search query to prevent injection attacks"""
    if not query:
        return query

    # Remove potentially dangerous FTS operators and syntax
    # Allow only alphanumeric, spaces, and basic punctuation
    # Remove FTS special characters: " * ( ) : - AND OR NOT NEAR
    dangerous_chars = ['*', '(', ')', ':', '"', '-', "'"]
    sanitized = query

    for char in dangerous_chars:
        sanitized = sanitized.replace(char, ' ')

    # Remove FTS operator keywords by replacing with spaces
    operators = ['AND', 'OR', 'NOT', 'NEAR']
    for op in operators:
        sanitized = sanitized.replace(f' {op} ', ' ')
        sanitized = sanitized.replace(f' {op.lower()} ', ' ')

    # Collapse multiple spaces and trim
    sanitized = ' '.join(sanitized.split())

    return sanitized

def process_post_content(content):
    """Process post content like make_omnibus: decode quoted-printable and convert markdown to HTML"""
    # Step 1: Decode quoted-printable encoding
    try:
        decoded_content = quopri.decodestring(content.encode('utf-8')).decode('utf-8')
    except:
        decoded_content = content
    
    # Step 1.5: Skip first line (date/category info) as it's redundant with metadata
    lines = decoded_content.strip().split('\n')
    if lines and lines[0].startswith('#'):
        # Skip the first line which is just date/category
        decoded_content = '\n'.join(lines[1:]).strip()
    
    # Step 2: Convert markdown to HTML (without nl2br to handle line breaks properly)
    html_content = markdown.markdown(decoded_content)
    
    # Step 3: Format for table layout (like make_omnibus sed command)
    # s,^<h1,</td></tr><tr><td><h1,;s,/h1>$,/h1></td><td>,
    html_content = re.sub(r'^<h1', '</td></tr><tr><td><h1', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'/h1>$', '/h1></td><td>', html_content, flags=re.MULTILINE)
    
    # Step 4: Load pandoc.css and wrap content
    try:
        with open(PANDOC_CSS_PATH, 'r', encoding='utf-8') as f:
            css_content = f.read()
    except:
        css_content = ""
    
    # Wrap in table structure like make_omnibus
    full_html = f"""
    {css_content}
    <table>
    <tr><td></td><td>
    {html_content}
    </td></tr>
    </table>
    """
    
    return full_html

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/timeline')
def api_timeline():
    """Get timeline data for visualization"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get monthly post counts
    cursor.execute('''
        SELECT year, month, category, COUNT(*) as count
        FROM posts 
        GROUP BY year, month, category
        ORDER BY year, month
    ''')
    
    timeline_data = {}
    for row in cursor.fetchall():
        year_month = f"{row['year']}-{row['month']:02d}"
        if year_month not in timeline_data:
            timeline_data[year_month] = {'A': 0, 'D': 0, 'AHNS': 0, 'J': 0, 'US': 0, 'total': 0}
        
        category = row['category']
        count = row['count']
        timeline_data[year_month][category] = count
        
        # Add A and D to US total
        if category in ['A', 'D']:
            timeline_data[year_month]['US'] += count
            
        timeline_data[year_month]['total'] += count
    
    # Get date range
    cursor.execute('SELECT MIN(date) as min_date, MAX(date) as max_date FROM posts')
    date_range = cursor.fetchone()
    
    conn.close()
    
    return jsonify({
        'timeline': timeline_data,
        'date_range': {
            'start': date_range['min_date'],
            'end': date_range['max_date']
        }
    })

@app.route('/api/posts')
def api_posts():
    """Get filtered posts"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get query parameters
    category = request.args.get('category', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    search = request.args.get('search', '')

    # Validate and sanitize limit parameter
    try:
        limit = int(request.args.get('limit', 50))
        # Cap limit to prevent DoS and ensure it's positive
        limit = max(1, min(limit, 1000))
    except (ValueError, TypeError):
        limit = 50

    # Validate and sanitize offset parameter
    try:
        offset = int(request.args.get('offset', 0))
        # Ensure offset is non-negative
        offset = max(0, offset)
    except (ValueError, TypeError):
        offset = 0
    
    # Build query
    conditions = []
    params = []
    
    if category:
        if category == 'US':
            conditions.append('posts.category IN (?, ?)')
            params.extend(['A', 'D'])
        else:
            conditions.append('posts.category = ?')
            params.append(category)
    
    if start_date:
        conditions.append('posts.date >= ?')
        params.append(start_date)
    
    if end_date:
        # Make end_date inclusive by treating it as < next_day
        try:
            # Parse the date and add one day
            date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            next_day = date_obj + timedelta(days=1)
            conditions.append('posts.date < ?')
            params.append(next_day.strftime('%Y-%m-%d'))
        except ValueError:
            # Fallback to original behavior if date parsing fails
            conditions.append('posts.date <= ?')
            params.append(end_date)
    
    if search:
        # Sanitize search query to prevent FTS injection
        sanitized_search = sanitize_fts_query(search)
        if not sanitized_search:
            # Return empty results if search is empty after sanitization
            conn.close()
            return jsonify({
                'posts': [],
                'total': 0,
                'limit': limit,
                'offset': offset
            })

        # Use FTS for search, sorted by date ascending
        if conditions:
            where_clause = 'AND ' + ' AND '.join(conditions)
            query = '''
                SELECT posts.*, posts_fts.rank
                FROM posts_fts
                JOIN posts ON posts.id = posts_fts.rowid
                WHERE posts_fts MATCH ?
                ''' + where_clause + '''
                ORDER BY date ASC
                LIMIT ? OFFSET ?
            '''
        else:
            query = '''
                SELECT posts.*, posts_fts.rank
                FROM posts_fts
                JOIN posts ON posts.id = posts_fts.rowid
                WHERE posts_fts MATCH ?
                ORDER BY date ASC
                LIMIT ? OFFSET ?
            '''
        cursor.execute(query, [sanitized_search] + params + [limit, offset])
    else:
        # Regular query
        if conditions:
            where_clause = 'WHERE ' + ' AND '.join(conditions)
            query = 'SELECT * FROM posts ' + where_clause + ' ORDER BY date ASC LIMIT ? OFFSET ?'
        else:
            query = 'SELECT * FROM posts ORDER BY date ASC LIMIT ? OFFSET ?'
        cursor.execute(query, params + [limit, offset])
    
    posts = []
    for row in cursor.fetchall():
        posts.append({
            'id': row['id'],
            'filename': row['filename'],
            'date': row['date'],
            'category': row['category'],
            'title': row['title'],
            'excerpt': row['excerpt'],
            'year': row['year'],
            'month': row['month'],
            'day': row['day']
        })
    
    # Get total count
    if search:
        if conditions:
            where_clause = 'AND ' + ' AND '.join(conditions)
            count_query = '''
                SELECT COUNT(*)
                FROM posts_fts
                JOIN posts ON posts.id = posts_fts.rowid
                WHERE posts_fts MATCH ?
                ''' + where_clause
        else:
            count_query = '''
                SELECT COUNT(*)
                FROM posts_fts
                JOIN posts ON posts.id = posts_fts.rowid
                WHERE posts_fts MATCH ?
            '''
        cursor.execute(count_query, [sanitized_search] + params)
    else:
        if conditions:
            where_clause = 'WHERE ' + ' AND '.join(conditions)
            count_query = 'SELECT COUNT(*) FROM posts ' + where_clause
        else:
            count_query = 'SELECT COUNT(*) FROM posts'
        cursor.execute(count_query, params)
    
    total = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'posts': posts,
        'total': total,
        'limit': limit,
        'offset': offset
    })

@app.route('/api/post/<int:post_id>')
def api_post(post_id):
    """Get single post with full content"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM posts WHERE id = ?', [post_id])
    row = cursor.fetchone()
    
    if not row:
        return jsonify({'error': 'Post not found'}), 404
    
    # Get search context from query parameters
    category = request.args.get('category', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    search = request.args.get('search', '')
    
    # Build conditions for navigation within search results
    conditions = []
    params = []
    
    if category:
        if category == 'US':
            conditions.append('posts.category IN (?, ?)')
            params.extend(['A', 'D'])
        else:
            conditions.append('posts.category = ?')
            params.append(category)
    
    if start_date:
        conditions.append('posts.date >= ?')
        params.append(start_date)
    
    if end_date:
        # Make end_date inclusive by treating it as < next_day
        try:
            # Parse the date and add one day
            date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            next_day = date_obj + timedelta(days=1)
            conditions.append('posts.date < ?')
            params.append(next_day.strftime('%Y-%m-%d'))
        except ValueError:
            # Fallback to original behavior if date parsing fails
            conditions.append('posts.date <= ?')
            params.append(end_date)
    
    # Get adjacent posts within search context
    if search:
        # Sanitize search query to prevent FTS injection
        sanitized_search = sanitize_fts_query(search)

        if sanitized_search:
            # Previous post in search results (earlier date)
            if conditions:
                where_clause = 'AND ' + ' AND '.join(conditions)
                prev_query = '''
                    SELECT posts.id, posts.title, posts.date
                    FROM posts_fts
                    JOIN posts ON posts.id = posts_fts.rowid
                    WHERE posts_fts MATCH ? AND posts.date < ?
                    ''' + where_clause + '''
                    ORDER BY posts.date DESC
                    LIMIT 1
                '''
            else:
                prev_query = '''
                    SELECT posts.id, posts.title, posts.date
                    FROM posts_fts
                    JOIN posts ON posts.id = posts_fts.rowid
                    WHERE posts_fts MATCH ? AND posts.date < ?
                    ORDER BY posts.date DESC
                    LIMIT 1
                '''
            cursor.execute(prev_query, [sanitized_search, row['date']] + params)
            prev_post = cursor.fetchone()

            # Next post in search results (later date)
            if conditions:
                where_clause = 'AND ' + ' AND '.join(conditions)
                next_query = '''
                    SELECT posts.id, posts.title, posts.date
                    FROM posts_fts
                    JOIN posts ON posts.id = posts_fts.rowid
                    WHERE posts_fts MATCH ? AND posts.date > ?
                    ''' + where_clause + '''
                    ORDER BY posts.date ASC
                    LIMIT 1
                '''
            else:
                next_query = '''
                    SELECT posts.id, posts.title, posts.date
                    FROM posts_fts
                    JOIN posts ON posts.id = posts_fts.rowid
                    WHERE posts_fts MATCH ? AND posts.date > ?
                    ORDER BY posts.date ASC
                    LIMIT 1
                '''
            cursor.execute(next_query, [sanitized_search, row['date']] + params)
            next_post = cursor.fetchone()
        else:
            # If search is empty after sanitization, no navigation
            prev_post = None
            next_post = None
    else:
        # Regular navigation within filtered results
        if conditions:
            where_clause = 'WHERE ' + ' AND '.join(conditions) + ' AND date < ?'
            prev_query = 'SELECT id, title, date FROM posts ' + where_clause + ' ORDER BY date DESC LIMIT 1'
        else:
            prev_query = 'SELECT id, title, date FROM posts WHERE date < ? ORDER BY date DESC LIMIT 1'
        cursor.execute(prev_query, params + [row['date']])
        prev_post = cursor.fetchone()

        # Next post (later date)
        if conditions:
            where_clause = 'WHERE ' + ' AND '.join(conditions) + ' AND date > ?'
            next_query = 'SELECT id, title, date FROM posts ' + where_clause + ' ORDER BY date ASC LIMIT 1'
        else:
            next_query = 'SELECT id, title, date FROM posts WHERE date > ? ORDER BY date ASC LIMIT 1'
        cursor.execute(next_query, params + [row['date']])
        next_post = cursor.fetchone()
    
    conn.close()
    
    # Process content like make_omnibus
    html_content = process_post_content(row['content'])
    
    post = {
        'id': row['id'],
        'filename': row['filename'],
        'date': row['date'],
        'category': row['category'],
        'title': row['title'],
        'content': row['content'],
        'html_content': html_content,
        'year': row['year'],
        'month': row['month'],
        'day': row['day']
    }
    
    result = {'post': post}
    
    if prev_post:
        result['prev'] = {
            'id': prev_post['id'],
            'title': prev_post['title'],
            'date': prev_post['date']
        }
    
    if next_post:
        result['next'] = {
            'id': next_post['id'],
            'title': next_post['title'],
            'date': next_post['date']
        }
    
    # Add search context for highlighting
    if search:
        # Extract search terms, handling quoted phrases
        try:
            result['search_terms'] = shlex.split(search)
        except ValueError:
            result['search_terms'] = search.replace('"', '').replace("'", '').split()
    
    return jsonify(result)

@app.route('/api/search/suggestions')
def api_search_suggestions():
    """Get search suggestions"""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get common words/phrases from cleaned titles and content
    cursor.execute('''
        SELECT clean_title, clean_content FROM posts 
        WHERE clean_title LIKE ? OR clean_content LIKE ?
        LIMIT 10
    ''', [f'%{query}%', f'%{query}%'])
    
    suggestions = set()
    for row in cursor.fetchall():
        # Simple word extraction for suggestions from cleaned text
        text = (row['clean_title'] or '') + ' ' + (row['clean_content'] or '')
        words = text.lower().split()
        for word in words:
            if query.lower() in word and len(word) > 2:
                suggestions.add(word)
        if len(suggestions) >= 10:
            break
    
    conn.close()
    
    return jsonify(list(suggestions)[:10])

@app.route('/api/stats')
def api_stats():
    """Get database statistics"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Total posts
    cursor.execute('SELECT COUNT(*) FROM posts')
    total_posts = cursor.fetchone()[0]
    
    # Category breakdown
    cursor.execute('SELECT category, COUNT(*) FROM posts GROUP BY category')
    raw_categories = dict(cursor.fetchall())
    
    # Combine A and D into US for display
    categories = {}
    us_count = 0
    for cat, count in raw_categories.items():
        if cat in ['A', 'D']:
            us_count += count
            categories[cat] = count  # Keep individual A and D counts
        else:
            categories[cat] = count
    categories['US'] = us_count  # Add combined US count
    
    # Date range
    cursor.execute('SELECT MIN(date), MAX(date) FROM posts')
    date_range = cursor.fetchone()
    
    # Posts per year
    cursor.execute('SELECT year, COUNT(*) FROM posts GROUP BY year ORDER BY year')
    yearly_counts = dict(cursor.fetchall())
    
    conn.close()
    
    return jsonify({
        'total_posts': total_posts,
        'categories': categories,
        'date_range': {
            'start': date_range[0].split('T')[0],
            'end': date_range[1].split('T')[0]
        },
        'yearly_counts': yearly_counts
    })

@app.route('/api/photos/<date>')
def api_photos(date):
    """Get photos for a specific date"""
    try:
        # Validate date format
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    date_photos_dir = PHOTOS_DIR / date
    cached = True

    # Fetch photos if they are not already cached
    if not (date_photos_dir.exists() and any(date_photos_dir.glob('*.jpg'))):
        try:
            fetch_photos_for_date(date)
            cached = False
        except PhotoFetchTimeout as exc:
            return jsonify({
                'date': date,
                'photos': [],
                'error': str(exc),
                'cached': False
            }), 500
        except PhotoFetchError as exc:
            return jsonify({
                'date': date,
                'photos': [],
                'error': str(exc),
                'cached': False
            }), 500
        except Exception as exc:
            return jsonify({
                'date': date,
                'photos': [],
                'error': f'Unexpected error: {exc}',
                'cached': False
            }), 500
    
    # Gather photo filenames after ensuring directory exists
    if date_photos_dir.exists():
        photo_files = sorted(f.name for f in date_photos_dir.glob('*.jpg'))
    else:
        photo_files = []

    return jsonify({
        'date': date,
        'photos': photo_files,
        'cached': cached
    })

@app.route('/photos/<date>/<filename>')
def serve_photo(date, filename):
    """Serve photo files"""
    try:
        # Validate date format
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    # Security: ensure filename is just a filename (no path traversal)
    if '/' in filename or '\\' in filename or filename.startswith('.'):
        return jsonify({'error': 'Invalid filename'}), 400

    # Only allow alphanumeric, dash, underscore, and dot in filename
    if not all(c.isalnum() or c in '.-_' for c in filename):
        return jsonify({'error': 'Invalid filename'}), 400

    # Construct path and resolve to prevent path traversal
    photo_path = (PHOTOS_DIR / date / filename).resolve()

    # Ensure the resolved path is within PHOTOS_DIR
    try:
        photo_path.relative_to(PHOTOS_DIR.resolve())
    except ValueError:
        return jsonify({'error': 'Invalid path'}), 403

    if not photo_path.exists():
        return jsonify({'error': 'Photo not found'}), 404

    # Verify it's a file, not a directory
    if not photo_path.is_file():
        return jsonify({'error': 'Invalid resource'}), 403

    return send_file(photo_path, mimetype='image/jpeg')

if __name__ == '__main__':
    # Run indexer at startup (only in the reloader process to avoid running twice)
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        print("Starting Zoolog Web Interface...")
        if not index_posts():
            print("Failed to index posts. Check that the posts directory exists.")
            exit(1)
        print("\nStarting Flask server on http://localhost:8000")
        webbrowser.open('http://localhost:8000')

    app.run(debug=True, port=8000)
