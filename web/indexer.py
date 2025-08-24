#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "markdown>=3.5.1",
# ]
# ///
"""
Family log indexer - builds searchable database from posts
"""
import os
import re
import sqlite3
import quopri
from datetime import datetime
from pathlib import Path
import markdown

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
    
    return {
        'filename': filename,
        'date': post_date,
        'category': category,
        'title': title,
        'content': content_text,
        'excerpt': excerpt,
        'year': post_date.year,
        'month': post_date.month,
        'day': post_date.day
    }

def create_database(db_path):
    """Create the posts database with FTS support"""
    conn = sqlite3.connect(db_path)
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
            excerpt TEXT,
            year INTEGER,
            month INTEGER,
            day INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Full-text search virtual table
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
            filename, title, content, category,
            content='posts',
            content_rowid='id'
        )
    ''')
    
    # Triggers to keep FTS in sync
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN
            INSERT INTO posts_fts(rowid, filename, title, content, category)
            VALUES (new.id, new.filename, new.title, new.content, new.category);
        END
    ''')
    
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS posts_ad AFTER DELETE ON posts BEGIN
            INSERT INTO posts_fts(posts_fts, rowid, filename, title, content, category)
            VALUES('delete', old.id, old.filename, old.title, old.content, old.category);
        END
    ''')
    
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS posts_au AFTER UPDATE ON posts BEGIN
            INSERT INTO posts_fts(posts_fts, rowid, filename, title, content, category)
            VALUES('delete', old.id, old.filename, old.title, old.content, old.category);
            INSERT INTO posts_fts(rowid, filename, title, content, category)
            VALUES (new.id, new.filename, new.title, new.content, new.category);
        END
    ''')
    
    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_date ON posts(date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_year_month ON posts(year, month)')
    
    conn.commit()
    return conn

def index_posts(posts_dir, db_path):
    """Index all posts in the posts directory"""
    posts_path = Path(posts_dir)
    if not posts_path.exists():
        print(f"Posts directory not found: {posts_dir}")
        return
    
    # Create web directory if it doesn't exist
    web_dir = Path(db_path).parent
    web_dir.mkdir(exist_ok=True)
    
    conn = create_database(db_path)
    cursor = conn.cursor()
    
    # Clear existing data
    cursor.execute('DELETE FROM posts')
    conn.commit()
    
    indexed_count = 0
    error_count = 0
    
    print(f"Indexing posts from {posts_dir}...")
    
    for txt_file in posts_path.glob('*.txt'):
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            post_info = extract_post_info(txt_file.name, content)
            if post_info:
                cursor.execute('''
                    INSERT INTO posts (filename, date, category, title, content, excerpt, year, month, day)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    post_info['filename'],
                    post_info['date'].isoformat(),
                    post_info['category'],
                    post_info['title'],
                    post_info['content'],
                    post_info['excerpt'],
                    post_info['year'],
                    post_info['month'],
                    post_info['day']
                ))
                indexed_count += 1
                
                if indexed_count % 100 == 0:
                    print(f"Indexed {indexed_count} posts...")
                    conn.commit()
            else:
                print(f"Could not parse: {txt_file.name}")
                error_count += 1
                
        except Exception as e:
            print(f"Error processing {txt_file.name}: {e}")
            error_count += 1
    
    conn.commit()
    
    # Get stats
    cursor.execute('SELECT COUNT(*) FROM posts')
    total_posts = cursor.fetchone()[0]
    
    cursor.execute('SELECT MIN(date), MAX(date) FROM posts')
    date_range = cursor.fetchone()
    
    cursor.execute('SELECT category, COUNT(*) FROM posts GROUP BY category ORDER BY category')
    category_stats = cursor.fetchall()
    
    conn.close()
    
    print(f"\nIndexing complete!")
    print(f"Total posts indexed: {total_posts}")
    print(f"Errors: {error_count}")
    print(f"Date range: {date_range[0]} to {date_range[1]}")
    print(f"Categories:")
    for cat, count in category_stats:
        print(f"  {cat}: {count} posts")

if __name__ == '__main__':
    script_dir = Path(__file__).parent
    posts_dir = script_dir.parent / 'posts'
    db_path = script_dir / 'zoolog.db'
    
    index_posts(str(posts_dir), str(db_path))