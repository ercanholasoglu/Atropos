#pragma once

#include "board/state.hpp"
#include "transposition_table/transposition_table.hpp"
#include "uci/options.hpp"

#include <atomic>
#include <iosfwd>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace atropos::uci {

class Engine {
public:
  ~Engine();

  void run(std::istream &input, std::ostream &output, std::ostream &diagnostics);
  void handle_line(const std::string &line, std::ostream &output, std::ostream &diagnostics);
  void wait_for_search_idle();

  [[nodiscard]] const EngineOptions &options() const noexcept { return options_; }
  [[nodiscard]] const std::string &position_text() const noexcept { return position_text_; }
  [[nodiscard]] const board::Position &position() const noexcept { return position_; }
  [[nodiscard]] bool quit_requested() const noexcept { return quit_requested_; }
  [[nodiscard]] bool pondering() const noexcept { return pondering_; }

private:
  void write_identification(std::ostream &output) const;
  void handle_setoption(const std::vector<std::string> &args, std::ostream &diagnostics);
  void handle_position(const std::vector<std::string> &args, std::ostream &diagnostics);
  void handle_go(const std::vector<std::string> &args, std::ostream &output,
                 std::ostream &diagnostics);
  void handle_perft(const std::vector<std::string> &args, std::ostream &output,
                    std::ostream &diagnostics) const;
  void handle_bench(const std::vector<std::string> &args, std::ostream &output,
                    std::ostream &diagnostics);
  void handle_selfplay(const std::vector<std::string> &args, std::ostream &output,
                       std::ostream &diagnostics);
  void request_search_stop();

  EngineOptions options_;
  board::Position position_ = board::Position::startpos();
  std::shared_ptr<tt::TranspositionTable> transposition_table_ =
      std::make_shared<tt::TranspositionTable>(options_.hash_mb);
  std::string position_text_ = "startpos";
  bool quit_requested_ = false;
  bool pondering_ = false;
  std::shared_ptr<std::atomic_bool> search_stop_;
  std::thread search_worker_;
  std::mutex output_mutex_;
};

} // namespace atropos::uci
