#include "uci/engine.hpp"

#include "benchmark/bench.hpp"
#include "board/types.hpp"
#include "movegen/movegen.hpp"
#include "perft/perft.hpp"
#include "search/search.hpp"
#include "strength/selfplay.hpp"
#include "uci/command.hpp"

#include <algorithm>
#include <charconv>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <sstream>

namespace atropos::uci {
namespace {

[[nodiscard]] std::string join_range(const std::vector<std::string> &words, std::size_t first) {
  std::ostringstream out;
  for (std::size_t i = first; i < words.size(); ++i) {
    if (i != first) {
      out << ' ';
    }
    out << words[i];
  }
  return out.str();
}

[[nodiscard]] bool has_go_limit(const std::vector<std::string> &args) {
  static constexpr std::string_view limits[] = {"depth", "nodes", "movetime", "wtime", "btime",
                                                "movestogo", "infinite", "ponder", "perft"};
  return std::any_of(args.begin(), args.end(), [](const std::string &arg) {
    return std::any_of(std::begin(limits), std::end(limits),
                       [&arg](std::string_view limit) { return arg == limit; });
  });
}

[[nodiscard]] std::optional<int> parse_depth(std::string_view text) {
  int value = 0;
  const auto *begin = text.data();
  const auto *end = text.data() + text.size();
  const auto result = std::from_chars(begin, end, value);
  if (result.ec != std::errc{} || result.ptr != end || value < 0) {
    return std::nullopt;
  }
  return value;
}

[[nodiscard]] std::optional<std::uint64_t> parse_uint64(std::string_view text) {
  std::uint64_t value = 0;
  const auto *begin = text.data();
  const auto *end = text.data() + text.size();
  const auto result = std::from_chars(begin, end, value);
  if (result.ec != std::errc{} || result.ptr != end) {
    return std::nullopt;
  }
  return value;
}

[[nodiscard]] std::optional<board::Move> find_legal_uci_move(const board::Position &position,
                                                             const std::string &text) {
  const auto legal = movegen::generate_legal_moves(position);
  const auto found = std::find_if(legal.begin(), legal.end(), [&text](board::Move move) {
    return board::move_to_uci(move) == text;
  });
  if (found == legal.end()) {
    return std::nullopt;
  }
  return *found;
}

[[nodiscard]] std::optional<std::size_t> find_token(const std::vector<std::string> &args,
                                                    std::string_view token) {
  const auto found = std::find(args.begin(), args.end(), token);
  if (found == args.end()) {
    return std::nullopt;
  }
  return static_cast<std::size_t>(std::distance(args.begin(), found));
}

[[nodiscard]] std::optional<int> find_depth_limit(const std::vector<std::string> &args) {
  const auto depth_index = find_token(args, "depth");
  if (!depth_index.has_value() || *depth_index + 1 >= args.size()) {
    return std::nullopt;
  }
  return parse_depth(args[*depth_index + 1]);
}

[[nodiscard]] std::optional<std::uint64_t> find_uint64_after(const std::vector<std::string> &args,
                                                            std::string_view token) {
  const auto index = find_token(args, token);
  if (!index.has_value() || *index + 1 >= args.size()) {
    return std::nullopt;
  }
  return parse_uint64(args[*index + 1]);
}

[[nodiscard]] bool has_token(const std::vector<std::string> &args, std::string_view token) {
  return find_token(args, token).has_value();
}

[[nodiscard]] search::SearchLimits make_search_limits(const std::vector<std::string> &args,
                                                      board::Color side_to_move) {
  search::SearchLimits limits;
  const bool open_ended = has_token(args, "infinite") || has_token(args, "ponder");
  limits.depth = find_depth_limit(args).value_or(open_ended ? 64 : 4);

  if (const auto nodes = find_uint64_after(args, "nodes"); nodes.has_value()) {
    limits.nodes = std::max<std::uint64_t>(1, *nodes);
  }

  std::optional<std::uint64_t> move_time = find_uint64_after(args, "movetime");
  if (!move_time.has_value()) {
    move_time = side_to_move == board::Color::White ? find_uint64_after(args, "wtime")
                                                    : find_uint64_after(args, "btime");
    if (move_time.has_value()) {
      const auto increment = side_to_move == board::Color::White ? find_uint64_after(args, "winc")
                                                                 : find_uint64_after(args, "binc");
      const auto moves_to_go = find_uint64_after(args, "movestogo").value_or(30);
      const auto divisor = std::max<std::uint64_t>(1, moves_to_go);
      const auto base = *move_time / divisor;
      const auto bonus = increment.value_or(0) / 2;
      const auto cap = std::max<std::uint64_t>(1, *move_time / 4);
      move_time = std::max<std::uint64_t>(1, std::min(base + bonus, cap));
    }
  }
  if (move_time.has_value()) {
    limits.deadline =
        std::chrono::steady_clock::now() + std::chrono::milliseconds(static_cast<int>(*move_time));
  }

  return limits;
}

[[nodiscard]] std::string pv_to_uci(const std::vector<board::Move> &pv) {
  std::ostringstream out;
  for (std::size_t i = 0; i < pv.size(); ++i) {
    if (i != 0) {
      out << ' ';
    }
    out << board::move_to_uci(pv[i]);
  }
  return out.str();
}

void write_search_info(std::ostream &output, const search::SearchResult &result) {
  output << "info depth " << result.depth << " score cp " << result.score << " nodes "
         << result.nodes;
  if (result.tt_hits != 0) {
    output << " tthits " << result.tt_hits;
  }
  if (result.killer_updates != 0) {
    output << " killers " << result.killer_updates;
  }
  if (result.history_updates != 0) {
    output << " history " << result.history_updates;
  }
  if (result.stopped) {
    output << " string limit";
  }
  if (!result.principal_variation.empty()) {
    output << " pv " << pv_to_uci(result.principal_variation);
  }
  output << '\n';
}

void write_bestmove(std::ostream &output, const search::SearchResult &result) {
  if (!result.best_move.has_value()) {
    output << "bestmove 0000\n";
    return;
  }
  output << "bestmove " << board::move_to_uci(*result.best_move) << '\n';
}

} // namespace

Engine::~Engine() {
  request_search_stop();
  wait_for_search_idle();
}

void Engine::wait_for_search_idle() {
  if (search_worker_.joinable()) {
    search_worker_.join();
  }
}

void Engine::request_search_stop() {
  if (search_stop_ != nullptr) {
    search_stop_->store(true, std::memory_order_relaxed);
  }
}

void Engine::run(std::istream &input, std::ostream &output, std::ostream &diagnostics) {
  std::string line;
  while (!quit_requested_ && std::getline(input, line)) {
    handle_line(line, output, diagnostics);
  }
}

void Engine::handle_line(const std::string &line, std::ostream &output, std::ostream &diagnostics) {
  const auto command = parse_command(line);
  if (command.name.empty()) {
    return;
  }

  if (command.name == "uci") {
    write_identification(output);
    return;
  }
  if (command.name == "isready") {
    output << "readyok\n";
    return;
  }
  if (command.name == "ucinewgame") {
    request_search_stop();
    wait_for_search_idle();
    position_ = board::Position::startpos();
    transposition_table_->clear();
    position_text_ = "startpos";
    return;
  }
  if (command.name == "position") {
    handle_position(command.args, diagnostics);
    return;
  }
  if (command.name == "setoption") {
    handle_setoption(command.args, diagnostics);
    return;
  }
  if (command.name == "go") {
    handle_go(command.args, output, diagnostics);
    return;
  }
  if (command.name == "perft") {
    handle_perft(command.args, output, diagnostics);
    return;
  }
  if (command.name == "bench") {
    handle_bench(command.args, output, diagnostics);
    return;
  }
  if (command.name == "selfplay") {
    handle_selfplay(command.args, output, diagnostics);
    return;
  }
  if (command.name == "ponderhit") {
    pondering_ = false;
    return;
  }
  if (command.name == "stop") {
    request_search_stop();
    wait_for_search_idle();
    pondering_ = false;
    return;
  }
  if (command.name == "quit") {
    request_search_stop();
    wait_for_search_idle();
    quit_requested_ = true;
    return;
  }

  diagnostics << "info string ignoring unknown command: " << command.name << '\n';
}

void Engine::write_identification(std::ostream &output) const {
  output << "id name Atropos 0.0.1\n";
  output << "id author Atropos contributors\n";
  for (const auto &option : describe_options()) {
    output << "option name " << option.name << " type " << option.type << " default "
           << option.default_value;
    if (option.min.has_value()) {
      output << " min " << *option.min;
    }
    if (option.max.has_value()) {
      output << " max " << *option.max;
    }
    output << '\n';
  }
  output << "uciok\n";
}

void Engine::handle_setoption(const std::vector<std::string> &args, std::ostream &diagnostics) {
  auto name_it = std::find(args.begin(), args.end(), "name");
  if (name_it == args.end() || std::next(name_it) == args.end()) {
    diagnostics << "info string malformed setoption: missing name\n";
    return;
  }

  auto value_it = std::find(args.begin(), args.end(), "value");
  const auto name_begin = static_cast<std::size_t>(std::distance(args.begin(), std::next(name_it)));
  const auto name_end =
      value_it == args.end() ? args.size() : static_cast<std::size_t>(std::distance(args.begin(), value_it));

  std::ostringstream name;
  for (std::size_t i = name_begin; i < name_end; ++i) {
    if (i != name_begin) {
      name << ' ';
    }
    name << args[i];
  }

  const std::string value =
      value_it == args.end() || std::next(value_it) == args.end()
          ? ""
          : join_range(args, static_cast<std::size_t>(std::distance(args.begin(), std::next(value_it))));

  if (!set_option(options_, name.str(), value)) {
    diagnostics << "info string rejected setoption name " << name.str() << '\n';
    return;
  }
  if (name.str() == "Hash") {
    request_search_stop();
    wait_for_search_idle();
    transposition_table_->resize(options_.hash_mb);
  }
}

void Engine::handle_position(const std::vector<std::string> &args, std::ostream &diagnostics) {
  request_search_stop();
  wait_for_search_idle();
  transposition_table_->clear();

  if (args.empty()) {
    diagnostics << "info string malformed position command\n";
    return;
  }

  if (args.front() == "startpos") {
    position_text_ = join_range(args, 0);
    position_ = board::Position::startpos();
    const auto moves_index = find_token(args, "moves");
    if (moves_index.has_value()) {
      for (std::size_t i = *moves_index + 1; i < args.size(); ++i) {
        const auto move = find_legal_uci_move(position_, args[i]);
        if (!move.has_value() || !position_.make_move(*move).has_value()) {
          diagnostics << "info string rejected illegal move in position command: " << args[i] << '\n';
          return;
        }
      }
    }
    return;
  }

  if (args.front() == "fen") {
    const auto moves_index = find_token(args, "moves");
    const std::size_t fen_end = moves_index.value_or(args.size());
    if (fen_end < 7) {
      diagnostics << "info string malformed position fen command\n";
      return;
    }
    std::ostringstream fen;
    for (std::size_t i = 1; i < 7; ++i) {
      if (i != 1) {
        fen << ' ';
      }
      fen << args[i];
    }
    const auto parsed = board::Position::from_fen(fen.str());
    if (!parsed.has_value()) {
      diagnostics << "info string rejected malformed FEN\n";
      return;
    }
    position_ = *parsed;
    position_text_ = join_range(args, 0);
    if (moves_index.has_value()) {
      for (std::size_t i = *moves_index + 1; i < args.size(); ++i) {
        const auto move = find_legal_uci_move(position_, args[i]);
        if (!move.has_value() || !position_.make_move(*move).has_value()) {
          diagnostics << "info string rejected illegal move in position command: " << args[i] << '\n';
          return;
        }
      }
    }
    return;
  }

  diagnostics << "info string unsupported position form\n";
}

void Engine::handle_go(const std::vector<std::string> &args, std::ostream &output,
                       std::ostream &diagnostics) {
  request_search_stop();
  wait_for_search_idle();

  if (!args.empty() && args.front() == "perft") {
    handle_perft(std::vector<std::string>{std::next(args.begin()), args.end()}, output, diagnostics);
    return;
  }

  if (!args.empty() && !has_go_limit(args)) {
    diagnostics << "info string go command has no recognized Phase 12 limit\n";
  }

  const auto limits = make_search_limits(args, position_.side_to_move());
  pondering_ = has_token(args, "ponder");
  auto async_limits = limits;
  search_stop_ = std::make_shared<std::atomic_bool>(false);
  async_limits.stop = search_stop_;
  async_limits.transposition_table = transposition_table_;
  auto position = position_;
  search_worker_ = std::thread([this, position, async_limits, &output]() mutable {
    const auto result = search::search_iterative(
        position, async_limits, [this, &output](const search::SearchResult &depth_result) {
          std::lock_guard<std::mutex> lock(output_mutex_);
          write_search_info(output, depth_result);
        });
    std::lock_guard<std::mutex> lock(output_mutex_);
    write_bestmove(output, result);
  });
}

void Engine::handle_perft(const std::vector<std::string> &args, std::ostream &output,
                          std::ostream &diagnostics) const {
  if (args.empty()) {
    diagnostics << "info string malformed perft command: missing depth\n";
    return;
  }

  const auto depth = parse_depth(args.front());
  if (!depth.has_value()) {
    diagnostics << "info string malformed perft depth: " << args.front() << '\n';
    return;
  }

  auto copy = position_;
  std::uint64_t total = 0;
  for (const auto &entry : perft::divide(copy, *depth)) {
    output << board::move_to_uci(entry.move) << ": " << entry.nodes << '\n';
    total += entry.nodes;
  }
  output << "nodes " << (*depth == 0 ? perft::count_nodes(copy, *depth) : total) << '\n';
}

void Engine::handle_bench(const std::vector<std::string> &args, std::ostream &output,
                          std::ostream &diagnostics) {
  request_search_stop();
  wait_for_search_idle();

  int depth = 3;
  if (!args.empty()) {
    const auto parsed = parse_depth(args.front());
    if (!parsed.has_value()) {
      diagnostics << "info string malformed bench depth: " << args.front() << '\n';
      return;
    }
    depth = *parsed;
  }

  const auto result = benchmark::run(depth);
  output << "bench depth " << result.depth << " positions " << result.positions << " nodes "
         << result.nodes << " tthits " << result.tt_hits << " elapsedms " << result.elapsed_ms
         << '\n';
}

void Engine::handle_selfplay(const std::vector<std::string> &args, std::ostream &output,
                             std::ostream &diagnostics) {
  request_search_stop();
  wait_for_search_idle();

  strength::SelfPlayConfig config;
  if (!args.empty()) {
    const auto games = parse_depth(args[0]);
    if (!games.has_value() || *games <= 0) {
      diagnostics << "info string malformed selfplay games: " << args[0] << '\n';
      return;
    }
    config.games = *games;
  }
  if (args.size() >= 2) {
    const auto depth = parse_depth(args[1]);
    if (!depth.has_value()) {
      diagnostics << "info string malformed selfplay depth: " << args[1] << '\n';
      return;
    }
    config.depth = *depth;
  }
  if (args.size() >= 3) {
    const auto max_plies = parse_depth(args[2]);
    if (!max_plies.has_value() || *max_plies <= 0) {
      diagnostics << "info string malformed selfplay maxplies: " << args[2] << '\n';
      return;
    }
    config.max_plies = *max_plies;
  }

  const auto result = strength::run_self_play(config);
  output << "selfplay games " << result.games << " depth " << result.depth << " maxplies "
         << result.max_plies << " plies " << result.plies << " whitewins "
         << result.white_wins << " blackwins " << result.black_wins << " draws "
         << result.draws << " score " << result.white_score_rate << " elo "
         << result.white_elo_difference << " nodes " << result.nodes << '\n';
}

} // namespace atropos::uci
