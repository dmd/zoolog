// Zoolog Web Interface JavaScript

class ZoologApp {
    constructor() {
        // Check URL parameters for initial values
        const urlParams = new URLSearchParams(window.location.search);
        const limitParam = urlParams.get('limit');
        const startDateParam = urlParams.get('start_date');
        const endDateParam = urlParams.get('end_date');
        const categoryParam = urlParams.get('category');
        const searchParam = urlParams.get('search');
        
        this.currentQuery = {
            search: searchParam || '',
            category: categoryParam || '',
            start_date: startDateParam || '',
            end_date: endDateParam || '',
            offset: 0,
            limit: limitParam ? parseInt(limitParam) : 200
        };
        this.posts = [];
        this.totalPosts = 0;
        this.currentPost = null;
        this.isLoading = false;
        this.selectedSuggestionIndex = -1;
        this.suggestions = [];
        this.currentPhotos = [];
        this.currentPhotoIndex = 0;
        this.loadedPhotosDates = []; // Track order of cached dates for LRU
        this.photosByDate = new Map(); // Store photos by date
        this.currentPhotoFetch = null; // Track current photo fetch request
        this.MAX_CACHED_DATES = 50; // Limit cache to 50 dates to prevent memory leak

        this.init();
    }
    
    init() {
        this.bindEvents();
        this.populateFormFromURLParams();
        this.loadStats();
        this.loadPosts();
    }
    
    bindEvents() {
        // Search
        const searchInput = document.getElementById('search-input');
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                const searchValue = e.target.value.trim();
                this.currentQuery.search = searchValue;
                this.currentQuery.offset = 0;
                this.loadPosts(true);

                // Only show suggestions if there's a search value
                if (searchValue) {
                    this.showSearchSuggestions(searchValue);
                } else {
                    this.hideSuggestions();
                }
            }, 300);
        });
        
        // Search input keyboard navigation
        searchInput.addEventListener('keydown', (e) => {
            if (this.suggestions.length === 0) return;
            
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                this.selectedSuggestionIndex = Math.min(this.selectedSuggestionIndex + 1, this.suggestions.length - 1);
                this.highlightSuggestion();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                this.selectedSuggestionIndex = Math.max(this.selectedSuggestionIndex - 1, -1);
                this.highlightSuggestion();
            } else if (e.key === 'Enter' && this.selectedSuggestionIndex >= 0) {
                e.preventDefault();
                this.selectSuggestion(this.suggestions[this.selectedSuggestionIndex]);
            } else if (e.key === 'Escape') {
                this.hideSuggestions();
            }
        });
        
        // Filters
        document.getElementById('category-filter').addEventListener('change', (e) => {
            this.currentQuery.category = e.target.value;
            this.currentQuery.offset = 0;
            this.loadPosts(true);
        });
        
        document.getElementById('start-date').addEventListener('change', (e) => {
            this.currentQuery.start_date = e.target.value;
            this.currentQuery.offset = 0;
            this.loadPosts(true);
        });
        
        document.getElementById('end-date').addEventListener('change', (e) => {
            this.currentQuery.end_date = e.target.value;
            this.currentQuery.offset = 0;
            this.loadPosts(true);
        });
        
        document.getElementById('clear-filters').addEventListener('click', () => {
            this.clearFilters();
        });
        
        
        // Infinite scroll on posts list container
        const postsList = document.getElementById('posts-list');
        postsList.addEventListener('scroll', () => {
            this.handleScroll();
        });
        
        // Post viewer navigation only
        
        document.getElementById('prev-post').addEventListener('click', () => {
            this.navigatePost('prev');
        });
        
        document.getElementById('next-post').addEventListener('click', () => {
            this.navigatePost('next');
        });
        
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Check if focus is on an input element
            const activeElement = document.activeElement;
            const isInputFocused = activeElement && (
                activeElement.tagName === 'INPUT' || 
                activeElement.tagName === 'SELECT' || 
                activeElement.tagName === 'TEXTAREA'
            );
            
            if (e.key === 'Escape') {
                // Check if lightbox is open first
                if (document.getElementById('photo-lightbox').style.display === 'flex') {
                    this.closeLightbox();
                } else {
                    this.closePost();
                }
            }
            
            // Check if lightbox is open for arrow key navigation
            if (document.getElementById('photo-lightbox').style.display === 'flex') {
                if (e.key === 'ArrowLeft') {
                    this.navigateLightbox('prev');
                    e.preventDefault();
                }
                if (e.key === 'ArrowRight') {
                    this.navigateLightbox('next');
                    e.preventDefault();
                }
            } else if (this.currentPost) {
                if (e.key === 'ArrowLeft') {
                    this.navigatePost('prev');
                }
                if (e.key === 'ArrowRight') {
                    this.navigatePost('next');
                }
                
                // Add j/k shortcuts when not focused on input elements
                if (!isInputFocused) {
                    if (e.key === 'j') {
                        e.preventDefault();
                        this.navigatePost('next'); // j goes to later post
                    }
                    if (e.key === 'k') {
                        e.preventDefault();
                        this.navigatePost('prev'); // k goes to earlier post
                    }
                }
            }
        });
        
        // Close suggestions when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.search-box')) {
                this.hideSuggestions();
            }
        });
        
        // Reset to show all posts when clicking Zoolog title
        document.querySelector('h1').addEventListener('click', () => {
            this.clearFilters();
        });
        
        
        document.getElementById('lightbox-close').addEventListener('click', () => {
            this.closeLightbox();
        });
        
        document.getElementById('lightbox-prev').addEventListener('click', () => {
            this.navigateLightbox('prev');
        });
        
        document.getElementById('lightbox-next').addEventListener('click', () => {
            this.navigateLightbox('next');
        });
        
        // Close lightbox on background click
        document.getElementById('photo-lightbox').addEventListener('click', (e) => {
            if (e.target.id === 'photo-lightbox') {
                this.closeLightbox();
            }
        });

    }
    
    populateFormFromURLParams() {
        // Populate form fields with values from URL parameters
        if (this.currentQuery.search) {
            document.getElementById('search-input').value = this.currentQuery.search;
        }
        if (this.currentQuery.category) {
            document.getElementById('category-filter').value = this.currentQuery.category;
        }
        if (this.currentQuery.start_date) {
            document.getElementById('start-date').value = this.currentQuery.start_date;
        }
        if (this.currentQuery.end_date) {
            document.getElementById('end-date').value = this.currentQuery.end_date;
        }
    }
    
    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const stats = await response.json();

            // Validate and initialize date pickers
            const startDate = stats.date_range?.start;
            const endDate = stats.date_range?.end;

            // Set start date: URL param, or stats value, or fallback
            if (!this.currentQuery.start_date) {
                if (startDate && this.isValidDate(startDate)) {
                    document.getElementById('start-date').value = startDate.split('T')[0];
                } else {
                    const tenYearsAgo = new Date();
                    tenYearsAgo.setFullYear(tenYearsAgo.getFullYear() - 10);
                    document.getElementById('start-date').value = tenYearsAgo.toISOString().split('T')[0];
                }
            } else if (!this.isValidDate(this.currentQuery.start_date)) {
                // Invalid URL parameter - reset it
                console.warn('Invalid start_date URL parameter, resetting to default');
                this.currentQuery.start_date = '';
                if (startDate && this.isValidDate(startDate)) {
                    document.getElementById('start-date').value = startDate.split('T')[0];
                }
            }

            // Set end date: URL param, or stats value, or fallback
            if (!this.currentQuery.end_date) {
                if (endDate && this.isValidDate(endDate)) {
                    document.getElementById('end-date').value = endDate.split('T')[0];
                } else {
                    const today = new Date();
                    document.getElementById('end-date').value = today.toISOString().split('T')[0];
                }
            } else if (!this.isValidDate(this.currentQuery.end_date)) {
                // Invalid URL parameter - reset it
                console.warn('Invalid end_date URL parameter, resetting to default');
                this.currentQuery.end_date = '';
                if (endDate && this.isValidDate(endDate)) {
                    document.getElementById('end-date').value = endDate.split('T')[0];
                }
            }
        } catch (error) {
            console.error('Error loading stats:', error);
            // Fallback: set date pickers to reasonable defaults if stats fail
            if (!this.currentQuery.start_date || !this.isValidDate(this.currentQuery.start_date)) {
                const tenYearsAgo = new Date();
                tenYearsAgo.setFullYear(tenYearsAgo.getFullYear() - 10);
                document.getElementById('start-date').value = tenYearsAgo.toISOString().split('T')[0];
                this.currentQuery.start_date = '';
            }
            if (!this.currentQuery.end_date || !this.isValidDate(this.currentQuery.end_date)) {
                const today = new Date();
                document.getElementById('end-date').value = today.toISOString().split('T')[0];
                this.currentQuery.end_date = '';
            }
        }
    }

    isValidDate(dateString) {
        // Check if date string matches YYYY-MM-DD format and is a valid date
        const regex = /^\d{4}-\d{2}-\d{2}(T.*)?$/;
        if (!regex.test(dateString)) return false;

        const date = new Date(dateString);
        return date instanceof Date && !isNaN(date.getTime());
    }
    
    
    async loadPosts(reset = false) {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoading();
        
        if (reset) {
            this.posts = [];
            this.currentQuery.offset = 0;
        }
        
        try {
            const params = new URLSearchParams(this.currentQuery);
            const response = await fetch(`/api/posts?${params}`);
            const data = await response.json();
            
            if (reset) {
                this.posts = data.posts;
            } else {
                this.posts.push(...data.posts);
            }
            
            this.totalPosts = data.total;
            this.renderPosts();
            this.updatePostCount();
            
        } catch (error) {
            console.error('Error loading posts:', error);
        } finally {
            this.isLoading = false;
            this.hideLoading();
        }
    }
    
    handleScroll() {
        if (this.isLoading || this.posts.length >= this.totalPosts) return;

        const postsList = document.getElementById('posts-list');
        const scrollTop = postsList.scrollTop;
        const scrollHeight = postsList.scrollHeight;
        const clientHeight = postsList.clientHeight;

        // Load more when user scrolls within 200px of bottom of posts list
        if (scrollTop + clientHeight >= scrollHeight - 200) {
            this.loadMorePosts();
        }
    }
    
    async loadMorePosts() {
        if (this.posts.length >= this.totalPosts) return;
        
        this.currentQuery.offset = this.posts.length;
        await this.loadPosts(false);
    }
    
    renderPosts() {
        const postsList = document.getElementById('posts-list');
        postsList.innerHTML = '';
        
        this.posts.forEach(post => {
            const postElement = this.createPostElement(post);
            postsList.appendChild(postElement);
        });
        
    }
    
    createPostElement(post) {
        const element = document.createElement('div');
        element.className = 'post-item';
        element.dataset.postId = post.id;
        
        const dateObj = new Date(post.date);
        const isoDate = dateObj.toISOString().split('T')[0];
        const dayOfWeek = dateObj.toLocaleDateString('en-US', { weekday: 'short' });
        const date = `${isoDate} ${dayOfWeek}`;
        
        element.innerHTML = `
            <div class="post-meta">
                <span class="post-date">${date}</span>
                <span class="post-category ${post.category.toLowerCase()}">${post.category}</span>
            </div>
            <div class="post-excerpt">${post.excerpt || 'No preview available'}</div>
        `;
        
        element.addEventListener('click', () => {
            this.openPost(post.id);
        });
        
        return element;
    }
    
    updatePostCount() {
        const countElement = document.getElementById('post-count');
        countElement.textContent = `(${this.posts.length} of ${this.totalPosts})`;
    }
    
    async openPost(postId) {
        this.showLoading();
        
        try {
            // Pass current search context to get correct prev/next posts
            const params = new URLSearchParams({
                search: this.currentQuery.search,
                category: this.currentQuery.category,
                start_date: this.currentQuery.start_date,
                end_date: this.currentQuery.end_date
            });
            
            const response = await fetch(`/api/post/${postId}?${params}`);
            const data = await response.json();
            
            if (data.error) {
                alert('Post not found');
                return;
            }
            
            this.currentPost = data;
            this.renderPost();
            this.highlightCurrentPost();
            this.showPostViewer();
            
            // Load photos for this date asynchronously (don't await)
            const postDate = data.post.date.split('T')[0]; // Extract YYYY-MM-DD from ISO datetime
            this.loadPhotos(postDate);
            
        } catch (error) {
            console.error('Error loading post:', error);
        } finally {
            this.hideLoading();
        }
    }
    
    highlightSearchTerms(html, searchTerms) {
        if (!searchTerms || searchTerms.length === 0) return html;

        // Create a DOM parser to properly handle HTML
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        searchTerms.forEach(term => {
            if (term.length > 1) {
                // Escape special regex characters in the search term
                const escapedTerm = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const regex = new RegExp(`\\b(${escapedTerm})\\b`, 'gi');

                // Walk through all text nodes
                const walker = document.createTreeWalker(
                    doc.body,
                    NodeFilter.SHOW_TEXT,
                    null
                );

                const textNodes = [];
                let node;
                while (node = walker.nextNode()) {
                    // Skip text nodes inside script, style, or mark tags
                    const parent = node.parentElement;
                    if (parent && !['SCRIPT', 'STYLE', 'MARK'].includes(parent.tagName)) {
                        textNodes.push(node);
                    }
                }

                // Replace matches in text nodes
                textNodes.forEach(textNode => {
                    const text = textNode.textContent;
                    if (regex.test(text)) {
                        const span = document.createElement('span');
                        span.innerHTML = text.replace(regex, '<mark class="search-highlight">$1</mark>');
                        textNode.replaceWith(...span.childNodes);
                    }
                });
            }
        });

        return doc.body.innerHTML;
    }
    
    renderPost() {
        if (!this.currentPost) return;
        
        const post = this.currentPost.post;
        const postContent = document.getElementById('post-content');
        
        const dateObj = new Date(post.date);
        const isoDate = dateObj.toISOString().split('T')[0];
        const dayOfWeek = dateObj.toLocaleDateString('en-US', { weekday: 'short' });
        const date = `${isoDate} ${dayOfWeek}`;
        
        // Highlight search terms if they exist
        let htmlContent = post.html_content;
        if (this.currentPost.search_terms) {
            htmlContent = this.highlightSearchTerms(htmlContent, this.currentPost.search_terms);
        }
        
        postContent.innerHTML = `
            <div class="post-meta">
                <span class="post-date">${date}</span>
                <span class="post-category ${post.category.toLowerCase()}">${post.category}</span>
            </div>
            <div class="post-text">${htmlContent}</div>
        `;
        
        // Update navigation buttons
        document.getElementById('prev-post').disabled = !this.currentPost.prev;
        document.getElementById('next-post').disabled = !this.currentPost.next;
    }
    
    showPostViewer() {
        const viewer = document.getElementById('post-viewer');
        viewer.style.display = 'block';
        
        // On mobile, show full screen
        if (window.innerWidth <= 768) {
            document.body.style.overflow = 'hidden';
        }
    }
    
    closePost() {
        const viewer = document.getElementById('post-viewer');
        viewer.style.display = 'none';
        this.currentPost = null;
        this.clearPostHighlight();
        // Don't hide photos - let them persist for browsing
        // User can close photos panel separately if needed

        document.body.style.overflow = '';
    }
    
    async navigatePost(direction) {
        if (!this.currentPost) return;
        
        const targetPost = this.currentPost[direction];
        if (!targetPost) return;
        
        await this.openPost(targetPost.id);
    }
    
    async showSearchSuggestions(query) {
        if (query.length < 2) {
            this.hideSuggestions();
            return;
        }
        
        try {
            const response = await fetch(`/api/search/suggestions?q=${encodeURIComponent(query)}`);
            const suggestions = await response.json();
            
            this.suggestions = suggestions;
            this.selectedSuggestionIndex = -1;
            this.renderSuggestions(suggestions);
        } catch (error) {
            console.error('Error loading suggestions:', error);
        }
    }
    
    renderSuggestions(suggestions) {
        const suggestionsEl = document.getElementById('search-suggestions');
        suggestionsEl.innerHTML = '';
        
        if (suggestions.length === 0) {
            this.hideSuggestions();
            return;
        }
        
        suggestions.forEach((suggestion, index) => {
            const element = document.createElement('div');
            element.className = 'suggestion';
            element.textContent = suggestion;
            element.dataset.index = index;
            
            element.addEventListener('click', () => {
                this.selectSuggestion(suggestion);
            });
            
            suggestionsEl.appendChild(element);
        });
        
        suggestionsEl.style.display = 'block';
    }
    
    hideSuggestions() {
        document.getElementById('search-suggestions').style.display = 'none';
        this.suggestions = [];
        this.selectedSuggestionIndex = -1;
    }
    
    highlightSuggestion() {
        const suggestionsEl = document.getElementById('search-suggestions');
        const suggestionElements = suggestionsEl.querySelectorAll('.suggestion');
        
        // Remove previous selection
        suggestionElements.forEach(el => el.classList.remove('selected'));
        
        // Highlight current selection
        if (this.selectedSuggestionIndex >= 0) {
            suggestionElements[this.selectedSuggestionIndex].classList.add('selected');
        }
    }
    
    selectSuggestion(suggestion) {
        document.getElementById('search-input').value = suggestion;
        this.currentQuery.search = suggestion;
        this.currentQuery.offset = 0;
        this.loadPosts(true);
        this.hideSuggestions();
    }
    
    async clearFilters() {
        document.getElementById('search-input').value = '';
        document.getElementById('category-filter').value = '';

        // Get limit from URL params
        const urlParams = new URLSearchParams(window.location.search);
        const limitParam = urlParams.get('limit');

        this.currentQuery = {
            search: '',
            category: '',
            start_date: '',
            end_date: '',
            offset: 0,
            limit: limitParam ? parseInt(limitParam) : 200
        };

        // Reload stats to reset date range pickers
        await this.loadStats();

        // Sync currentQuery with the date picker values after loadStats
        this.currentQuery.start_date = document.getElementById('start-date').value;
        this.currentQuery.end_date = document.getElementById('end-date').value;

        this.loadPosts(true);
    }
    
    
    showLoading() {
        document.getElementById('loading').style.display = 'flex';
    }
    
    hideLoading() {
        document.getElementById('loading').style.display = 'none';
    }
    
    highlightCurrentPost() {
        if (!this.currentPost) return;

        // Clear previous highlights
        this.clearPostHighlight();

        // Find and highlight the current post in the list
        const postElement = document.querySelector(`[data-post-id="${this.currentPost.post.id}"]`);
        if (postElement) {
            postElement.classList.add('active');

            // Scroll the post into view if it's not visible, but preserve relative position
            const postsList = document.getElementById('posts-list');
            const postsListRect = postsList.getBoundingClientRect();
            const postRect = postElement.getBoundingClientRect();

            // Only scroll if the post is not visible in the viewport
            if (postRect.top < postsListRect.top || postRect.bottom > postsListRect.bottom) {
                // Calculate the scroll position to center the post
                const scrollTop = postsList.scrollTop;
                const elementOffsetTop = postElement.offsetTop;
                const centerOffset = (postsList.clientHeight - postElement.clientHeight) / 2;

                postsList.scrollTop = elementOffsetTop - centerOffset;
            }
        }
    }
    
    clearPostHighlight() {
        const activePost = document.querySelector('.post-item.active');
        if (activePost) {
            activePost.classList.remove('active');
        }
    }
    
    cachePhotos(date, photos) {
        // Implement LRU cache eviction when limit is reached
        if (this.loadedPhotosDates.length >= this.MAX_CACHED_DATES) {
            // Remove the oldest cached date (first in array)
            const oldestDate = this.loadedPhotosDates.shift();
            this.photosByDate.delete(oldestDate);
        }

        // Remove date from array if it already exists (to update its position)
        const existingIndex = this.loadedPhotosDates.indexOf(date);
        if (existingIndex !== -1) {
            this.loadedPhotosDates.splice(existingIndex, 1);
        }

        // Add to end of array (most recently used)
        this.photosByDate.set(date, photos);
        this.loadedPhotosDates.push(date);
    }

    async loadPhotos(date) {
        if (this.loadedPhotosDates.includes(date)) {
            // Photos for this date already loaded, just show them
            this.showPhotos(date);
            return;
        }

        // Cancel any pending photo fetch
        if (this.currentPhotoFetch) {
            this.currentPhotoFetch.abort();
        }

        // Show photos panel and loading state
        this.showPhotosLoading(date);

        // Create an AbortController for this fetch
        const controller = new AbortController();
        this.currentPhotoFetch = controller;

        try {
            const response = await fetch(`/api/photos/${date}`, {
                signal: controller.signal
            });

            // Check if this request was aborted while waiting
            if (this.currentPhotoFetch !== controller) {
                return; // Another request has taken over
            }

            const data = await response.json();

            // Double-check we're still the active request
            if (this.currentPhotoFetch !== controller) {
                return;
            }

            if (data.photos && data.photos.length > 0) {
                const photos = data.photos.map(filename => ({
                    filename: filename,
                    url: `/photos/${date}/${filename}`,
                    date: date
                }));
                this.cachePhotos(date, photos);
                this.currentPhotos = photos;
                this.renderPhotos(date);
            } else {
                this.cachePhotos(date, []);
                this.currentPhotos = [];
                this.showPhotosEmpty();
            }
        } catch (error) {
            // Ignore abort errors
            if (error.name === 'AbortError') {
                return;
            }
            console.error('Error loading photos:', error);
            // Only show error if this is still the active request
            if (this.currentPhotoFetch === controller) {
                this.showPhotosEmpty();
            }
        } finally {
            // Clear the current fetch reference if it's still this controller
            if (this.currentPhotoFetch === controller) {
                this.currentPhotoFetch = null;
            }
        }
    }
    
    showPhotosLoading(date) {
        const photosPanel = document.getElementById('photos-panel');
        const photosLoading = document.getElementById('photos-loading');
        const photosList = document.getElementById('photos-list');
        const photosEmpty = document.getElementById('photos-empty');
        
        photosPanel.style.display = 'block';
        photosLoading.style.display = 'flex';
        photosList.innerHTML = '';
        photosEmpty.style.display = 'none';
        
        // Add class to main content for grid layout
        document.querySelector('.main-content').classList.add('with-photos');
    }
    
    showPhotos(date) {
        const photosPanel = document.getElementById('photos-panel');
        
        photosPanel.style.display = 'block';
        
        // Add class to main content for grid layout
        document.querySelector('.main-content').classList.add('with-photos');
        
        // Set current photos to the photos for this specific date
        this.currentPhotos = this.photosByDate.get(date) || [];
        this.renderPhotos(date);
    }
    
    renderPhotos(date) {
        const photosLoading = document.getElementById('photos-loading');
        const photosList = document.getElementById('photos-list');
        const photosEmpty = document.getElementById('photos-empty');
        
        photosLoading.style.display = 'none';
        photosEmpty.style.display = 'none';
        
        photosList.innerHTML = '';
        
        this.currentPhotos.forEach((photo, index) => {
            const img = document.createElement('img');
            img.src = photo.url;
            img.alt = `Photo from ${date}`;
            img.className = 'photo-thumbnail';
            img.dataset.index = index;
            
            img.addEventListener('click', () => {
                this.showLightbox(index);
            });
            
            photosList.appendChild(img);
        });
    }
    
    showPhotosEmpty() {
        const photosLoading = document.getElementById('photos-loading');
        const photosList = document.getElementById('photos-list');
        const photosEmpty = document.getElementById('photos-empty');
        
        photosLoading.style.display = 'none';
        photosList.innerHTML = '';
        photosEmpty.style.display = 'flex';
    }
    
    hidePhotos() {
        const photosPanel = document.getElementById('photos-panel');
        photosPanel.style.display = 'none';
        
        // Remove class from main content
        document.querySelector('.main-content').classList.remove('with-photos');
    }
    
    showLightbox(photoIndex) {
        if (photoIndex < 0 || photoIndex >= this.currentPhotos.length) return;
        
        this.currentPhotoIndex = photoIndex;
        const photo = this.currentPhotos[photoIndex];
        
        const lightbox = document.getElementById('photo-lightbox');
        const lightboxImage = document.getElementById('lightbox-image');
        const prevBtn = document.getElementById('lightbox-prev');
        const nextBtn = document.getElementById('lightbox-next');
        
        lightboxImage.src = photo.url;
        lightboxImage.alt = `Photo from ${photo.date}`;
        
        prevBtn.disabled = photoIndex === 0;
        nextBtn.disabled = photoIndex === this.currentPhotos.length - 1;
        
        lightbox.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
    
    closeLightbox() {
        const lightbox = document.getElementById('photo-lightbox');
        lightbox.style.display = 'none';
        document.body.style.overflow = '';
    }
    
    navigateLightbox(direction) {
        const newIndex = direction === 'prev' 
            ? this.currentPhotoIndex - 1 
            : this.currentPhotoIndex + 1;
            
        if (newIndex >= 0 && newIndex < this.currentPhotos.length) {
            this.showLightbox(newIndex);
        }
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ZoologApp();
});