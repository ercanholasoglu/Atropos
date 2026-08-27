#include "uci/command.hpp"

#include <cctype>
#include <sstream>

namespace atropos::uci {

std::string trim(std::string_view text) {
  auto begin = text.begin();
  auto end = text.end();

  while (begin != end && std::isspace(static_cast<unsigned char>(*begin)) != 0) {
    ++begin;
  }
  while (begin != end && std::isspace(static_cast<unsigned char>(*(end - 1))) != 0) {
    --end;
  }
  return std::string(begin, end);
}

std::vector<std::string> split_words(std::string_view text) {
  std::istringstream input{std::string(text)};
  std::vector<std::string> words;
  std::string word;
  while (input >> word) {
    words.push_back(word);
  }
  return words;
}

Command parse_command(std::string_view line) {
  const auto words = split_words(trim(line));
  if (words.empty()) {
    return {};
  }

  Command command;
  command.name = words.front();
  command.args.assign(words.begin() + 1, words.end());
  return command;
}

} // namespace atropos::uci
