#include "uci/engine.hpp"

#include <iostream>

int main() {
  // UCI output must reach the GUI the moment it is written.
  //
  // Without this the engine cannot play a game over a pipe. std::cin is tied
  // to std::cout by default, so replies written on the reader thread happen
  // to be flushed by the next read — which is why the `uci` handshake works.
  // The search runs on a worker thread and writes `info` and `bestmove`
  // asynchronously, with no read following to flush them, so they sit in the
  // buffer until the process exits. A GUI waits for a `bestmove` that never
  // comes, and the engine loses on time on move one.
  std::cout << std::unitbuf;

  atropos::uci::Engine engine;
  engine.run(std::cin, std::cout, std::cerr);
  return 0;
}
