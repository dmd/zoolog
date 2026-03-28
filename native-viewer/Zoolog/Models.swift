import Foundation
import SwiftUI

struct Post: Identifiable, Hashable {
    let id: Int
    let filename: String
    let date: Date
    let dateString: String
    let category: String
    let title: String
    let content: String
    let excerpt: String
    let year: Int
    let month: Int
    let day: Int

    var displayDate: String {
        let fmt = DateFormatter()
        fmt.dateFormat = "yyyy-MM-dd EEE"
        return fmt.string(from: date)
    }

    func hash(into hasher: inout Hasher) { hasher.combine(id) }
    static func == (lhs: Post, rhs: Post) -> Bool { lhs.id == rhs.id }
}

struct PostStats {
    var total: Int = 0
    var categories: [String: Int] = [:]
    var minDate: String = ""
    var maxDate: String = ""
}

enum Category: String, CaseIterable, Identifiable {
    case all = ""
    case us = "US"
    case a = "A"
    case d = "D"
    case j = "J"
    case ahns = "AHNS"

    var id: String { rawValue }

    var label: String {
        switch self {
        case .all: return "All"
        case .us: return "A+D"
        case .a: return "A"
        case .d: return "D"
        case .ahns: return "AHNS"
        case .j: return "Uncle J"
        }
    }

    var color: CategoryColor {
        switch self {
        case .all: return .gray
        case .us: return .blue
        case .a: return .green
        case .d: return .cyan
        case .ahns: return .purple
        case .j: return .orange
        }
    }
}

enum CategoryColor {
    case gray, blue, green, cyan, purple, orange

    var swiftUI: SwiftUI.Color {
        switch self {
        case .gray: return .secondary
        case .blue: return .blue
        case .green: return .green
        case .cyan: return .cyan
        case .purple: return .purple
        case .orange: return .orange
        }
    }
}

extension String {
    var categoryColor: SwiftUI.Color {
        switch self {
        case "A": return .green
        case "D": return .cyan
        case "AHNS": return .purple
        case "J": return .orange
        case "US": return .blue
        default: return .secondary
        }
    }
}
