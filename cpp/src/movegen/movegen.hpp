#pragma once

#include "board/state.hpp"

#include <vector>

namespace atropos::movegen {

[[nodiscard]] std::vector<board::Move> generate_legal_moves(const board::Position &position);
[[nodiscard]] std::vector<board::Move> generate_pseudo_legal_moves(const board::Position &position);
void generate_legal_moves_into(const board::Position &position, std::vector<board::Move> &moves);
void generate_legal_moves_into(const board::Position &position, std::vector<board::Move> &moves,
                               std::vector<board::Move> &pseudo);
void generate_pseudo_legal_moves_into(const board::Position &position, std::vector<board::Move> &moves);
[[nodiscard]] bool is_legal_move(const board::Position &position, board::Move move);

} // namespace atropos::movegen
