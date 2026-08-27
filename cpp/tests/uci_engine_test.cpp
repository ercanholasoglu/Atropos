#include "test.hpp"
#include "uci/engine.hpp"
#include "board/types.hpp"
#include "movegen/movegen.hpp"

#include <algorithm>
#include <sstream>
#include <string>

TEST_CASE("uci handshake emits valid mandatory lines") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("uci", out, err);
  const auto text = out.str();

  REQUIRE(text.find("id name Atropos") != std::string::npos);
  REQUIRE(text.find("option name Hash type spin default 16") != std::string::npos);
  REQUIRE(text.find("option name Threads type spin default 1") != std::string::npos);
  REQUIRE(text.find("option name Seed type spin default 0") != std::string::npos);
  REQUIRE(text.ends_with("uciok\n"));
  REQUIRE(err.str().empty());
}

TEST_CASE("isready always emits readyok") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("isready", out, err);

  REQUIRE_EQ(out.str(), "readyok\n");
}

TEST_CASE("setoption updates deterministic scaffold options") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("setoption name Hash value 32", out, err);
  engine.handle_line("setoption name Threads value 1", out, err);
  engine.handle_line("setoption name Seed value 12345", out, err);

  REQUIRE_EQ(engine.options().hash_mb, 32);
  REQUIRE_EQ(engine.options().threads, 1);
  REQUIRE_EQ(engine.options().seed, 12345U);
  REQUIRE(out.str().empty());
  REQUIRE(err.str().empty());
}

TEST_CASE("position commands are retained without board interpretation") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("position startpos moves e2e4 e7e5", out, err);
  REQUIRE_EQ(engine.position_text(), "startpos moves e2e4 e7e5");

  engine.handle_line("position fen 8/8/8/8/8/8/8/8 w - - 0 1", out, err);
  REQUIRE_EQ(engine.position_text(), "fen 8/8/8/8/8/8/8/8 w - - 0 1");
}

TEST_CASE("go depth returns search info and a legal bestmove") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("go depth 1", out, err);
  engine.wait_for_search_idle();

  const auto text = out.str();
  REQUIRE(text.find("info depth 1 score cp ") != std::string::npos);
  REQUIRE(text.find(" nodes ") != std::string::npos);
  REQUIRE(text.find(" pv ") != std::string::npos);
  REQUIRE(text.find("bestmove ") != std::string::npos);
  REQUIRE(err.str().empty());
}

TEST_CASE("go depth reports each completed iterative depth") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("go depth 3", out, err);
  engine.wait_for_search_idle();

  const auto text = out.str();
  REQUIRE(text.find("info depth 1 score cp ") != std::string::npos);
  REQUIRE(text.find("info depth 2 score cp ") != std::string::npos);
  REQUIRE(text.find("info depth 3 score cp ") != std::string::npos);
  REQUIRE(text.find(" killers ") != std::string::npos);
  REQUIRE(text.find(" history ") != std::string::npos);
  REQUIRE(text.find("bestmove ") != std::string::npos);
  REQUIRE(err.str().empty());
}

TEST_CASE("uci bestmove is legal for the current tested position") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("position startpos moves e2e4 e7e5", out, err);
  engine.handle_line("go depth 1", out, err);
  engine.wait_for_search_idle();

  const std::string prefix = "bestmove ";
  const auto text = out.str();
  const auto bestmove_index = text.find(prefix);
  REQUIRE(bestmove_index != std::string::npos);
  const auto bestmove = text.substr(bestmove_index + prefix.size(), 4);
  const auto legal = atropos::movegen::generate_legal_moves(engine.position());
  const auto found = std::find_if(legal.begin(), legal.end(), [&bestmove](atropos::board::Move move) {
    return atropos::board::move_to_uci(move) == bestmove;
  });
  REQUIRE(found != legal.end());
}

TEST_CASE("go depth prefers a material-winning capture") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("position fen 4k3/8/8/8/8/8/6q1/4K1R1 w - - 0 1", out, err);
  engine.handle_line("go depth 1", out, err);
  engine.wait_for_search_idle();

  REQUIRE(out.str().ends_with("bestmove g1g2\n"));
  REQUIRE(err.str().empty());
}

TEST_CASE("go nodes routes through search limits") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("go nodes 3", out, err);
  engine.wait_for_search_idle();

  const auto text = out.str();
  REQUIRE(text.find("info depth 1 score cp ") != std::string::npos);
  REQUIRE(text.find(" string limit") != std::string::npos);
  REQUIRE(text.find("bestmove ") != std::string::npos);
  REQUIRE(err.str().empty());
}

TEST_CASE("go movetime routes through search limits") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("go movetime 1", out, err);
  engine.wait_for_search_idle();

  REQUIRE(out.str().find("info depth 1 score cp ") != std::string::npos);
  REQUIRE(out.str().find(" string limit") != std::string::npos);
  REQUIRE(out.str().find("bestmove ") != std::string::npos);
  REQUIRE(err.str().empty());
}

TEST_CASE("go clock form uses bounded time allocation") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("go wtime 30 btime 30 winc 10 binc 10 movestogo 1", out, err);
  engine.wait_for_search_idle();

  REQUIRE(out.str().find("info depth 1 score cp ") != std::string::npos);
  REQUIRE(out.str().find(" string limit") != std::string::npos);
  REQUIRE(out.str().find("bestmove ") != std::string::npos);
  REQUIRE(err.str().empty());
}

TEST_CASE("go infinite searches until stop") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("go infinite", out, err);
  engine.handle_line("stop", out, err);

  const auto text = out.str();
  REQUIRE(text.find("info depth ") != std::string::npos);
  REQUIRE(text.find(" string limit") != std::string::npos);
  REQUIRE(text.find("bestmove ") != std::string::npos);
  REQUIRE(text.find("bestmove 0000") == std::string::npos);
  REQUIRE(err.str().empty());
}

TEST_CASE("ponderhit keeps ponder search running as normal search") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("go ponder", out, err);
  REQUIRE(engine.pondering());
  engine.handle_line("ponderhit", out, err);
  REQUIRE(!engine.pondering());
  engine.handle_line("stop", out, err);

  REQUIRE(out.str().find("bestmove ") != std::string::npos);
  REQUIRE(err.str().empty());
}

TEST_CASE("stop cancels an active search and emits a bestmove") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("go depth 10", out, err);
  engine.handle_line("stop", out, err);

  const auto text = out.str();
  REQUIRE(text.find(" string limit") != std::string::npos);
  REQUIRE(text.find("bestmove ") != std::string::npos);
  REQUIRE(text.find("bestmove 0000") == std::string::npos);
  REQUIRE(err.str().empty());
}

TEST_CASE("perft command reports divide lines and total nodes") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("perft 2", out, err);
  const auto text = out.str();

  REQUIRE(text.find("b1c3: 20\n") != std::string::npos);
  REQUIRE(text.ends_with("nodes 400\n"));
  REQUIRE(err.str().empty());
}

TEST_CASE("go perft uses the current position") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("position startpos moves e2e4", out, err);
  engine.handle_line("go perft 1", out, err);

  REQUIRE(out.str().ends_with("nodes 20\n"));
  REQUIRE(err.str().empty());
}

TEST_CASE("bench command reports aggregate search metrics") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("bench 2", out, err);

  const auto text = out.str();
  REQUIRE(text.find("bench depth 2 positions 5 nodes ") != std::string::npos);
  REQUIRE(text.find(" tthits ") != std::string::npos);
  REQUIRE(text.find(" elapsedms ") != std::string::npos);
  REQUIRE(err.str().empty());
}

TEST_CASE("selfplay command reports deterministic strength metrics") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("selfplay 1 0 4", out, err);

  const auto text = out.str();
  REQUIRE(text.find("selfplay games 1 depth 0 maxplies 4") != std::string::npos);
  REQUIRE(text.find(" whitewins ") != std::string::npos);
  REQUIRE(text.find(" blackwins ") != std::string::npos);
  REQUIRE(text.find(" draws ") != std::string::npos);
  REQUIRE(text.find(" elo ") != std::string::npos);
  REQUIRE(text.find(" nodes ") != std::string::npos);
  REQUIRE(err.str().empty());
}

TEST_CASE("unknown command writes diagnostics only to stderr stream") {
  atropos::uci::Engine engine;
  std::ostringstream out;
  std::ostringstream err;

  engine.handle_line("not_a_uci_command", out, err);

  REQUIRE(out.str().empty());
  REQUIRE(err.str().find("not_a_uci_command") != std::string::npos);
}
