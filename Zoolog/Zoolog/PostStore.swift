import Foundation
import SwiftUI
import Combine

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

    // Photos
    @Published var photos: [NSImage] = []
    @Published var isLoadingPhotos = false
    @Published var selectedPhotoIndex: Int?
    @Published var showLightbox = false

    // Posts directory
    @Published var postsDirectory: URL?

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

        // Try to auto-detect the posts directory
        autoDetectPostsDirectory()
    }

    // MARK: - Directory selection

    func autoDetectPostsDirectory() {
        // Look for posts/ relative to the executable or common locations
        let candidates = [
            Bundle.main.bundleURL.deletingLastPathComponent().appendingPathComponent("posts"),
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath).appendingPathComponent("posts"),
            FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("zoolog/posts"),
        ]

        for candidate in candidates {
            var isDir: ObjCBool = false
            if FileManager.default.fileExists(atPath: candidate.path, isDirectory: &isDir), isDir.boolValue {
                postsDirectory = candidate
                Task { await indexAndLoad() }
                return
            }
        }
    }

    func chooseDirectory() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        panel.message = "Select the 'posts' directory containing your Zoolog journal entries"
        panel.prompt = "Select"

        if panel.runModal() == .OK, let url = panel.url {
            postsDirectory = url
            Task { await indexAndLoad() }
        }
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
            endDate: fmt.string(from: endDate)
        )

        posts = result.posts
        totalPosts = result.total
        isLoading = false
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
        // Use macOS Shortcuts CLI to fetch photos (same approach as web app)
        let shortcutName = "photosondate"

        let tempDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try? FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: tempDir) }

        let outputPath = tempDir.appendingPathComponent("out")

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/shortcuts")
        process.arguments = ["run", shortcutName, "-i", dateStr, "-o", outputPath.path]
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice

        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return []
        }

        guard process.terminationStatus == 0 else { return [] }

        // Collect output files
        var candidates: [URL] = []
        var isDir: ObjCBool = false
        if FileManager.default.fileExists(atPath: outputPath.path, isDirectory: &isDir) {
            if isDir.boolValue {
                candidates = (try? FileManager.default.contentsOfDirectory(at: outputPath, includingPropertiesForKeys: nil)) ?? []
            } else {
                candidates = [outputPath]
            }
        }

        // Filter out videos, load as images
        let photoFiles = candidates
            .filter { $0.pathExtension.lowercased() != "mov" }
            .sorted(by: { $0.lastPathComponent < $1.lastPathComponent })

        var images: [NSImage] = []
        for file in photoFiles {
            // Resize using sips (built-in macOS tool) as a fallback to ImageMagick
            let resizedPath = tempDir.appendingPathComponent("\(file.lastPathComponent).jpg")

            let sips = Process()
            sips.executableURL = URL(fileURLWithPath: "/usr/bin/sips")
            sips.arguments = ["-s", "format", "jpeg", "--resampleWidth", "1000", file.path, "--out", resizedPath.path]
            sips.standardOutput = FileHandle.nullDevice
            sips.standardError = FileHandle.nullDevice

            do {
                try sips.run()
                sips.waitUntilExit()
            } catch { continue }

            let imageURL = sips.terminationStatus == 0 ? resizedPath : file
            if let image = NSImage(contentsOf: imageURL) {
                images.append(image)
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
