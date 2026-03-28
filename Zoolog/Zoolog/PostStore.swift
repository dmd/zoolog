import Foundation
import SwiftUI
import Combine
import Photos

@MainActor
final class PostStore: ObservableObject {
    // MARK: - Published state

    @Published var posts: [Post] = []
    @Published var totalPosts: Int = 0
    @Published var selectedPost: Post?
    @Published var stats: PostStats = PostStats()
    @Published var isLoading = false
    @Published var isIndexing = false
    @Published var indexingProgress: String = "Preparing..."
    @Published var hasIndexed = false
    @Published var focusSearch = false

    // Filters
    @Published var searchText: String = ""
    @Published var selectedCategory: Category = .all
    @Published var startDate: Date = Calendar.current.date(byAdding: .year, value: -20, to: Date())!
    @Published var endDate: Date = Date()

    // Font size
    @Published var fontSize: CGFloat = 19

    // Photos
    @Published var photos: [NSImage] = []
    @Published var isLoadingPhotos = false
    @Published var selectedPhotoIndex: Int?
    @Published var showLightbox = false

    // Posts directory
    @Published var postsDirectory: URL? = {
        let candidates = [
            "/Users/dmd/Dropbox/dashare/zoolog/posts",
            "/Users/asw/Dropbox (Personal)/dashare/zoolog/posts",
        ]
        for path in candidates {
            var isDir: ObjCBool = false
            if FileManager.default.fileExists(atPath: path, isDirectory: &isDir), isDir.boolValue {
                return URL(fileURLWithPath: path)
            }
        }
        return URL(fileURLWithPath: candidates[0])
    }()

    private let database = Database()
    private var searchDebounce: AnyCancellable?
    private var photoCache: [String: [NSImage]] = [:]

    init() {
        // Debounce search input
        searchDebounce = $searchText
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .removeDuplicates()
            .sink { [weak self] _ in
                Task { await self?.loadPosts() }
            }

        Task { await indexAndLoad() }
    }

    // MARK: - Indexing

    func indexAndLoad() async {
        guard let dir = postsDirectory else { return }

        isIndexing = true
        indexingProgress = "Indexing posts..."

        let count = await Task.detached { [database] in
            database.indexPosts(from: dir) { done, total in
                Task { @MainActor in
                    self.indexingProgress = "Indexing: \(done)/\(total) posts..."
                }
            }
        }.value

        stats = database.getStats()
        hasIndexed = true
        isIndexing = false

        if !stats.minDate.isEmpty {
            let fmt = DateFormatter()
            fmt.dateFormat = "yyyy-MM-dd"
            if let d = fmt.date(from: String(stats.minDate.prefix(10))) {
                startDate = d
            }
            if let d = fmt.date(from: String(stats.maxDate.prefix(10))) {
                endDate = d
            }
        }

        await loadPosts()
    }

    // MARK: - Loading

    func loadPosts() async {
        guard hasIndexed else { return }
        isLoading = true

        let fmt = DateFormatter()
        fmt.dateFormat = "yyyy-MM-dd"

        let result = database.queryPosts(
            search: searchText,
            category: selectedCategory.rawValue,
            startDate: fmt.string(from: startDate),
            endDate: fmt.string(from: endDate),
            limit: 500,
            offset: 0
        )

        posts = result.posts
        totalPosts = result.total
        isLoading = false
    }

    func loadMorePosts() async {
        guard hasIndexed, posts.count < totalPosts else { return }

        let fmt = DateFormatter()
        fmt.dateFormat = "yyyy-MM-dd"

        let result = database.queryPosts(
            search: searchText,
            category: selectedCategory.rawValue,
            startDate: fmt.string(from: startDate),
            endDate: fmt.string(from: endDate),
            limit: 500,
            offset: posts.count
        )

        posts.append(contentsOf: result.posts)
    }

    func applyFilters() {
        Task { await loadPosts() }
    }

    // MARK: - Navigation

    func selectPrevious() {
        guard let current = selectedPost,
              let idx = posts.firstIndex(of: current), idx > 0
        else { return }
        selectedPost = posts[idx - 1]
        loadPhotosForSelected()
    }

    func selectNext() {
        guard let current = selectedPost,
              let idx = posts.firstIndex(of: current), idx < posts.count - 1
        else { return }
        selectedPost = posts[idx + 1]
        loadPhotosForSelected()
    }

    func selectPost(_ post: Post) {
        selectedPost = post
        loadPhotosForSelected()
    }

    // MARK: - Photos

    func loadPhotosForSelected() {
        guard let post = selectedPost else {
            photos = []
            return
        }

        let dateStr = post.dateString

        // Check cache
        if let cached = photoCache[dateStr] {
            photos = cached
            return
        }

        photos = []
        isLoadingPhotos = true

        Task.detached { [weak self] in
            let images = await self?.fetchPhotos(for: dateStr) ?? []
            await MainActor.run {
                guard let self = self else { return }
                self.photos = images
                self.isLoadingPhotos = false

                // Cache with LRU eviction
                self.photoCache[dateStr] = images
                if self.photoCache.count > 50 {
                    if let oldest = self.photoCache.keys.sorted().first {
                        self.photoCache.removeValue(forKey: oldest)
                    }
                }
            }
        }
    }

    private func fetchPhotos(for dateStr: String) async -> [NSImage] {
        // Use PhotoKit to query Apple Photos directly
        let status = await PHPhotoLibrary.requestAuthorization(for: .readWrite)
        guard status == .authorized || status == .limited else { return [] }

        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone.current
        guard let startDate = formatter.date(from: dateStr) else { return [] }
        let endDate = Calendar.current.date(byAdding: .day, value: 1, to: startDate)!

        let fetchOptions = PHFetchOptions()
        fetchOptions.predicate = NSPredicate(
            format: "creationDate >= %@ AND creationDate < %@ AND mediaType == %d",
            startDate as NSDate, endDate as NSDate, PHAssetMediaType.image.rawValue
        )
        fetchOptions.sortDescriptors = [NSSortDescriptor(key: "creationDate", ascending: true)]

        let assets = PHAsset.fetchAssets(with: fetchOptions)
        guard assets.count > 0 else { return [] }

        let imageManager = PHImageManager.default()
        let options = PHImageRequestOptions()
        options.isSynchronous = true
        options.deliveryMode = .highQualityFormat
        options.resizeMode = .exact

        var images: [NSImage] = []
        let targetSize = CGSize(width: 1000, height: 1000)

        assets.enumerateObjects { asset, _, _ in
            imageManager.requestImage(
                for: asset,
                targetSize: targetSize,
                contentMode: .aspectFit,
                options: options
            ) { image, _ in
                if let image = image {
                    images.append(NSImage(cgImage: image.cgImage(forProposedRect: nil, context: nil, hints: nil)!, size: image.size))
                }
            }
        }

        return images
    }

    func openLightbox(at index: Int) {
        selectedPhotoIndex = index
        showLightbox = true
    }

    func closeLightbox() {
        showLightbox = false
        selectedPhotoIndex = nil
    }

    func nextPhoto() {
        guard let idx = selectedPhotoIndex, idx < photos.count - 1 else { return }
        selectedPhotoIndex = idx + 1
    }

    func previousPhoto() {
        guard let idx = selectedPhotoIndex, idx > 0 else { return }
        selectedPhotoIndex = idx - 1
    }
}
