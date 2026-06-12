import Foundation

struct ResponseParser {
    static let sharedDecoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .useDefaultKeys
        return d
    }()

    static func decode<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        try sharedDecoder.decode(type, from: data)
    }

    static func unwrapDataEnvelope<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        if let envelope = try? sharedDecoder.decode(DataEnvelope<T>.self, from: data) {
            return envelope.data
        }
        return try sharedDecoder.decode(type, from: data)
    }

    static func unwrapPageEnvelope<T: Decodable>(_ type: T.Type, from data: Data) throws -> (items: [T], page: PageInfo) {
        let envelope = try sharedDecoder.decode(PageEnvelope<T>.self, from: data)
        return (envelope.items, envelope.page)
    }

    static func unwrapItemsOnly<T: Decodable>(_ type: T.Type, from data: Data) throws -> [T] {
        if let envelope = try? sharedDecoder.decode(ItemsEnvelope<T>.self, from: data) {
            return envelope.items
        }
        if let items = try? sharedDecoder.decode([T].self, from: data) {
            return items
        }
        return []
    }

    static func parseError(from data: Data, statusCode: Int) -> FinanceApiError {
        if let errorResponse = try? sharedDecoder.decode(ErrorEnvelope.self, from: data) {
            return .httpError(statusCode: statusCode, message: errorResponse.error.message)
        }
        return .httpError(statusCode: statusCode, message: "HTTP ошибка \(statusCode)")
    }

    static func encode<T: Encodable>(_ value: T) throws -> Data {
        let encoder = JSONEncoder()
        return try encoder.encode(value)
    }
}

private struct DataEnvelope<T: Decodable>: Decodable {
    let data: T
}

private struct PageEnvelope<T: Decodable>: Decodable {
    let items: [T]
    let page: PageInfo
}

private struct ItemsEnvelope<T: Decodable>: Decodable {
    let items: [T]
}

private struct ErrorEnvelope: Decodable {
    let error: FinanceError
}
