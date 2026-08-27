#pragma once

#include <string>
#include <string_view>
#include <vector>

namespace atropos::uci {

struct Command {
  std::string name;
  std::vector<std::string> args;
};

[[nodiscard]] std::string trim(std::string_view text);
[[nodiscard]] std::vector<std::string> split_words(std::string_view text);
[[nodiscard]] Command parse_command(std::string_view line);

} // namespace atropos::uci
