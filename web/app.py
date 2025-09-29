#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "flask>=3.0.0",
#     "markdown>=3.5.1",
# ]
# ///
"""
Zoolog Web Interface - Flask backend

Security Notes:
- All endpoints are GET/read-only, so CSRF protection is not required
- If POST/PUT/DELETE endpoints are added in the future, implement CSRF protection
"""
import os
import sqlite3
import quopri
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file
import markdown

app = Flask(__name__)

# Configuration
DB_PATH = Path(__file__).parent / 'zoolog.db'
POSTS_DIR = Path(__file__).parent.parent / 'posts'
PANDOC_CSS_PATH = Path(__file__).parent.parent / 'pandoc.css'
PHOTOS_DIR = Path(__file__).parent / 'photos'
GET_DATE_PHOTOS_SCRIPT = Path(__file__).parent / 'get-date-photos'

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def sanitize_fts_query(query):
    """Sanitize FTS search query to prevent injection attacks"""
    if not query:
        return query

    # Remove potentially dangerous FTS operators and syntax
    # Allow only alphanumeric, spaces, and basic punctuation
    # Remove FTS special characters: " * ( ) : - AND OR NOT NEAR
    dangerous_chars = ['*', '(', ')', ':', '"', '-']
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
        result['search_terms'] = search.split()
    
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
    
    # Check if photos already exist for this date
    if date_photos_dir.exists() and any(date_photos_dir.glob('*.jpg')):
        # Photos exist, return them
        photo_files = [f.name for f in date_photos_dir.glob('*.jpg')]
        photo_files.sort()  # Sort for consistent ordering
        
        return jsonify({
            'date': date,
            'photos': photo_files,
            'cached': True
        })
    
    # Photos don't exist, run get-date-photos script
    try:
        # Run the script in the background
        result = subprocess.run(
            [str(GET_DATE_PHOTOS_SCRIPT), date],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=15  # 15 second timeout for better UX
        )
        
        if result.returncode == 0:
            # Script succeeded, get the photos
            if date_photos_dir.exists():
                photo_files = [f.name for f in date_photos_dir.glob('*.jpg')]
                photo_files.sort()
                
                return jsonify({
                    'date': date,
                    'photos': photo_files,
                    'cached': False
                })
            else:
                return jsonify({
                    'date': date,
                    'photos': [],
                    'cached': False
                })
        else:
            # Script failed or no photos found
            return jsonify({
                'date': date,
                'photos': [],
                'cached': False
            })
            
    except subprocess.TimeoutExpired:
        return jsonify({
            'date': date,
            'photos': [],
            'error': 'Photo fetch timeout',
            'cached': False
        }), 500
    except Exception as e:
        return jsonify({
            'date': date,
            'photos': [],
            'error': f'Error fetching photos: {str(e)}',
            'cached': False
        }), 500

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
    if not DB_PATH.exists():
        print("Database not found. Please run indexer.py first.")
        exit(1)
    
    app.run(debug=True, port=8000)