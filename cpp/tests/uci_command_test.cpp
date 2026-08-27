#include "test.hpp"
#include "uci/command.hpp"

TEST_CASE("uci command parser trims and splits input") {
  const auto command = atropos::uci::parse_command("  go depth 3  ");

  REQUIRE_EQ(command.name, "go");
  REQUIRE_EQ(command.args.size(), 2U);
  REQUIRE_EQ(command.args[0], "depth");
  REQUIRE_EQ(command.args[1], "3");
}

TEST_CASE("uci command parser handles empty input") {
  const auto command = atropos::uci::parse_command("   ");

  REQUIRE(command.name.empty());
  REQUIRE(command.args.empty());
}
