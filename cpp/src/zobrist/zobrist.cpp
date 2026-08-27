#include "zobrist/zobrist.hpp"

#include <array>
#include <cstdint>

namespace atropos::zobrist {
namespace {

[[nodiscard]] constexpr std::uint64_t splitmix64(std::uint64_t value) {
  value += 0x9e3779b97f4a7c15ULL;
  value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
  value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
  return value ^ (value >> 31U);
}

[[nodiscard]] constexpr int piece_index(board::Piece piece) {
  const int color_offset = piece.color == board::Color::White ? 0 : 6;
  int type = 0;
  switch (piece.type) {
  case board::PieceType::Pawn:
    type = 0;
    break;
  case board::PieceType::Knight:
    type = 1;
    break;
  case board::PieceType::Bishop:
    type = 2;
    break;
  case board::PieceType::Rook:
    type = 3;
    break;
  case board::PieceType::Queen:
    type = 4;
    break;
  case board::PieceType::King:
    type = 5;
    break;
  }
  return color_offset + type;
}

} // namespace

std::uint64_t piece_key(board::Piece piece, board::Square square) {
  return splitmix64(0x4154524f504f5300ULL + static_cast<std::uint64_t>(piece_index(piece) * 64 + square));
}

std::uint64_t side_key() { return splitmix64(0x4154524f504f53f0ULL); }

std::uint64_t castling_key(board::CastlingRights rights) {
  std::uint64_t key = 0;
  if (rights.white_king_side) {
    key ^= splitmix64(0x4154524f504f5401ULL);
  }
  if (rights.white_queen_side) {
    key ^= splitmix64(0x4154524f504f5402ULL);
  }
  if (rights.black_king_side) {
    key ^= splitmix64(0x4154524f504f5403ULL);
  }
  if (rights.black_queen_side) {
    key ^= splitmix64(0x4154524f504f5404ULL);
  }
  return key;
}

std::uint64_t en_passant_key(std::optional<board::Square> square) {
  if (!square.has_value()) {
    return 0;
  }
  return splitmix64(0x4154524f504f5500ULL + static_cast<std::uint64_t>(board::file_of(*square)));
}

} // namespace atropos::zobrist
