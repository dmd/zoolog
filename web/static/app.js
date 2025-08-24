// Zoolog Web Interface JavaScript

class ZoologApp {
    constructor() {
        this.currentQuery = {
            search: '',
            category: '',
            start_date: '',
            end_date: '',
            offset: 0,
            limit: 50
        };
        this.posts = [];
        this.totalPosts = 0;
        this.currentPost = null;
        this.isLoading = false;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
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
                this.currentQuery.search = e.target.value;
                this.currentQuery.offset = 0;
                this.loadPosts(true);
                this.showSearchSuggestions(e.target.value);
            }, 300);
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
            if (e.key === 'Escape') {
                this.closePost();
            }
            if (this.currentPost) {
                if (e.key === 'ArrowLeft') {
                    this.navigatePost('prev');
                }
                if (e.key === 'ArrowRight') {
                    this.navigatePost('next');
                }
            }
        });
        
        // Close suggestions when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.search-box')) {
                this.hideSuggestions();
            }
        });
    }
    
    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            const stats = await response.json();
            
            const statsText = `${stats.total_posts.toLocaleString()} posts • ${stats.date_range.start} to ${stats.date_range.end}`;
            document.getElementById('stats-text').textContent = statsText;
            
            // Initialize date pickers with ISO-8601 format
            document.getElementById('start-date').value = stats.date_range.start;
            document.getElementById('end-date').value = stats.date_range.end;
        } catch (error) {
            console.error('Error loading stats:', error);
        }
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
            const response = await fetch(`/api/post/${postId}`);
            const data = await response.json();
            
            if (data.error) {
                alert('Post not found');
                return;
            }
            
            this.currentPost = data;
            this.renderPost();
            this.showPostViewer();
            
        } catch (error) {
            console.error('Error loading post:', error);
        } finally {
            this.hideLoading();
        }
    }
    
    renderPost() {
        if (!this.currentPost) return;
        
        const post = this.currentPost.post;
        const postContent = document.getElementById('post-content');
        
        const dateObj = new Date(post.date);
        const isoDate = dateObj.toISOString().split('T')[0];
        const dayOfWeek = dateObj.toLocaleDateString('en-US', { weekday: 'short' });
        const date = `${isoDate} ${dayOfWeek}`;
        
        postContent.innerHTML = `
            <div class="post-meta">
                <span class="post-date">${date}</span>
                <span class="post-category ${post.category.toLowerCase()}">${post.category}</span>
            </div>
            <div class="post-text">${post.html_content}</div>
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
        
        suggestions.forEach(suggestion => {
            const element = document.createElement('div');
            element.className = 'suggestion';
            element.textContent = suggestion;
            
            element.addEventListener('click', () => {
                document.getElementById('search-input').value = suggestion;
                this.currentQuery.search = suggestion;
                this.currentQuery.offset = 0;
                this.loadPosts(true);
                this.hideSuggestions();
            });
            
            suggestionsEl.appendChild(element);
        });
        
        suggestionsEl.style.display = 'block';
    }
    
    hideSuggestions() {
        document.getElementById('search-suggestions').style.display = 'none';
    }
    
    clearFilters() {
        document.getElementById('search-input').value = '';
        document.getElementById('category-filter').value = '';
        document.getElementById('start-date').value = '';
        document.getElementById('end-date').value = '';
        
        this.currentQuery = {
            search: '',
            category: '',
            start_date: '',
            end_date: '',
            offset: 0,
            limit: 50
        };
        
        this.loadPosts(true);
    }
    
    
    showLoading() {
        document.getElementById('loading').style.display = 'flex';
    }
    
    hideLoading() {
        document.getElementById('loading').style.display = 'none';
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ZoologApp();
});