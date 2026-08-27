#pragma once

#include "board/state.hpp"

namespace atropos::evaluation {

[[nodiscard]] int piece_value(board::PieceType type) noexcept;
[[nodiscard]] int evaluate_material(const board::Position &position) noexcept;
[[nodiscard]] int evaluate(const board::Position &position) noexcept;

} // namespace atropos::evaluation
