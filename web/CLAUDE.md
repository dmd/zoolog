# Zoolog Web Interface

A Flask-based web application for browsing and searching family journal entries stored in a SQLite database.

## Features

- **Full-text search** with real-time suggestions and highlighting
- **Category filtering** (US/A+D, A, D, AHNS, Uncle J)
- **Date range filtering** with intuitive date pickers
- **Responsive design** with mobile support
- **Keyboard navigation** (j/k keys, arrow keys, Escape)
- **Infinite scroll** loading for large result sets
- **Post viewer** with navigation between search results
- **Search result highlighting** in post content

## Running the Application

1. Ensure you have a SQLite database (`zoolog.db`) created by running `indexer.py`
2. Start the Flask server:
   ```bash
   python app.py
   ```
3. Open http://localhost:8000 in your browser

## API Endpoints

### `/api/posts`
Get filtered posts with pagination.

**Query Parameters:**
- `search`: Full-text search query
- `category`: Filter by category (US, A, D, AHNS, J)
- `start_date`: Filter posts from this date (YYYY-MM-DD)
- `end_date`: Filter posts until this date (YYYY-MM-DD)  
- `limit`: Number of posts to return (default: 200, **useful for testing with MCP Playwright: `?limit=20`**)
- `offset`: Number of posts to skip for pagination

### `/api/post/<id>`
Get single post with full content and navigation context.

**Query Parameters:**
- Same filtering parameters as `/api/posts` to maintain search context for navigation

### `/api/timeline`
Get monthly post counts for visualization.

### `/api/stats`
Get database statistics (total posts, categories, date range).

### `/api/search/suggestions`
Get search suggestions based on query.

**Query Parameters:**
- `q`: Search query (minimum 2 characters)

## Special Query Parameters

### `limit` Parameter for Testing
When using MCP Playwright or other testing tools, add `?limit=20` to the URL to limit results and avoid token overflow:

```
http://localhost:8000?limit=20
```

This is especially useful since the default limit of 200 posts can cause issues with tools that have token limits.

## Architecture

- **Backend**: Flask (Python)
- **Frontend**: Vanilla JavaScript with modern CSS Grid/Flexbox
- **Database**: SQLite with FTS (Full-Text Search) extension
- **Content Processing**: Markdown to HTML conversion with quoted-printable decoding

## Search Interface

The interface features an ultra-compact design that maximizes content space:
- **Combined header/search section**: Title and all search controls in a single sticky bar
- **Minimal vertical whitespace**: Reduced padding and margins throughout
- **Single-line layout**: Search box, category dropdown, date filters, and clear button all on one line
- **Bottom-aligned elements**: All controls share the same baseline for clean visual alignment
- **Responsive design**: Adapts to mobile with stacked layout when needed

### Layout Features
- **Streamlined header**: Just the "Zoolog" title, bottom-aligned with controls
- **Expanded search box**: Maximum width available for search input with real-time suggestions
- **Efficient filters**: Category, date range, and clear button in compact arrangement
- **Sticky positioning**: Top section stays visible while scrolling
- **Clean baseline**: All elements aligned to the same bottom line for professional appearance

The ultra-compact design provides maximum screen real estate for browsing journal entries while keeping all functionality easily accessible. The removal of statistics text allows the search box to use the full available width.