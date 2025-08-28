# Zoolog Web Interface

A Flask-based web application for browsing and searching family journal entries stored in a SQLite database.

## Features

- **Full-text search** with real-time suggestions and highlighting
- **Category filtering** (US/A+D, A, D, AHNS, Uncle J)
- **Date range filtering** with intuitive date pickers
- **Photo viewer integration** with automatic photo loading for selected dates
- **Responsive design** with mobile support
- **Keyboard navigation** (j/k keys, arrow keys, Escape)
- **Infinite scroll** loading for large result sets
- **Post viewer** with navigation between search results
- **Search result highlighting** in post content
- **Lightbox photo viewer** with navigation and full-screen viewing
- **URL parameter support** for direct linking to filtered views

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

### `/api/photos/<date>`
Get photos for a specific date with intelligent caching.

**Path Parameters:**
- `date`: Date in YYYY-MM-DD format

**Response:**
- `photos`: Array of photo filenames
- `cached`: Boolean indicating if photos were cached or freshly fetched
- `error`: Error message if photo fetching failed

### `/photos/<date>/<filename>`
Serve photo files securely.

**Path Parameters:**
- `date`: Date in YYYY-MM-DD format
- `filename`: Photo filename (security validated)

## Special Query Parameters

### `limit` Parameter for Testing
When using MCP Playwright or other testing tools, add `?limit=20` to the URL to limit results and avoid token overflow:

```
http://localhost:8000?limit=20
```

This is especially useful since the default limit of 200 posts can cause issues with tools that have token limits.

### URL Parameter Support for Direct Linking
The application supports URL parameters for direct linking to filtered views:

**Supported URL Parameters:**
- `search`: Pre-populate search box and filter results
- `category`: Pre-select category filter (US, A, D, AHNS, J) 
- `start_date`: Pre-set start date filter (YYYY-MM-DD)
- `end_date`: Pre-set end date filter (YYYY-MM-DD)
- `limit`: Override default result limit

**Examples:**
```
# Filter to specific date range
http://localhost:8000?start_date=2016-03-10&end_date=2016-03-10

# Search with date range and category
http://localhost:8000?search=cards&start_date=2016-01-01&end_date=2016-12-31&category=AHNS

# Limited results for testing
http://localhost:8000?search=cooking&limit=10
```

URL parameters automatically populate form fields and apply filters on page load, enabling shareable links to specific filtered views.

## Architecture

- **Backend**: Flask (Python)
- **Frontend**: Vanilla JavaScript with modern CSS Grid/Flexbox
- **Database**: SQLite with FTS (Full-Text Search) extension
- **Content Processing**: Markdown to HTML conversion with quoted-printable decoding
- **Photo System**: Integration with `get-date-photos` script for fetching and caching photos
- **Image Processing**: Automatic resizing to 500px width with JPEG conversion

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

## Photo Integration

The application includes a seamless photo viewing experience:

### Photo Panel
- **Bottom panel layout**: Photos display in a horizontal scrollable panel at the bottom of the interface
- **Automatic loading**: Photos are fetched automatically when a post is selected
- **Smart caching**: Photos are cached locally to avoid redundant fetching
- **Asynchronous loading**: Photos load in the background without blocking the UI
- **Optimized dimensions**: 160px panel height with 150px thumbnails and minimal padding for efficient space usage

### Photo Features
- **Intelligent fetching**: Uses the `get-date-photos` script to fetch photos from external sources
- **Thumbnail display**: 150px square thumbnails with hover effects
- **Lightbox viewer**: Click any thumbnail to open full-screen lightbox with navigation
- **Keyboard support**: Escape key closes lightbox, arrow keys navigate between photos
- **Perfect centering**: Photos and navigation controls are precisely centered both horizontally and vertically
- **Error handling**: Graceful handling of missing photos or fetch failures

### Photo System Integration
- **External script integration**: Seamlessly integrates with `get-date-photos YYYY-MM-DD` script
- **Caching strategy**: Checks for existing photos before running external script
- **Image optimization**: All photos are resized and converted to JPEG format for optimal performance
- **Secure serving**: Photo files are served with proper security validation

The photo system enhances the journal browsing experience by providing visual context for each day's entries while maintaining the application's focus on efficient text browsing.