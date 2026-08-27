#pragma once

#include "board/types.hpp"

#include <array>
#include <cstdint>
#include <optional>

namespace atropos::zobrist {

[[nodiscard]] std::uint64_t piece_key(board::Piece piece, board::Square square);
[[nodiscard]] std::uint64_t side_key();
[[nodiscard]] std::uint64_t castling_key(board::CastlingRights rights);
[[nodiscard]] std::uint64_t en_passant_key(std::optional<board::Square> square);

} // namespace atropos::zobrist
