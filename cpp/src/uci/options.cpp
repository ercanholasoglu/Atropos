#include "uci/options.hpp"

#include <charconv>
#include <limits>

namespace atropos::uci {
namespace {

[[nodiscard]] std::optional<int> parse_int(std::string_view value) {
  int parsed = 0;
  const auto *begin = value.data();
  const auto *end = value.data() + value.size();
  const auto result = std::from_chars(begin, end, parsed);
  if (result.ec != std::errc{} || result.ptr != end) {
    return std::nullopt;
  }
  return parsed;
}

[[nodiscard]] std::optional<std::uint64_t> parse_uint64(std::string_view value) {
  std::uint64_t parsed = 0;
  const auto *begin = value.data();
  const auto *end = value.data() + value.size();
  const auto result = std::from_chars(begin, end, parsed);
  if (result.ec != std::errc{} || result.ptr != end) {
    return std::nullopt;
  }
  return parsed;
}

} // namespace

std::vector<UciOptionDescription> describe_options() {
  return {
      {.name = "Hash", .type = "spin", .default_value = "16", .min = 1, .max = 1048576},
      {.name = "Threads", .type = "spin", .default_value = "1", .min = 1, .max = 1},
      {.name = "Seed", .type = "spin", .default_value = "0", .min = 0, .max = std::nullopt},
  };
}

bool set_option(EngineOptions &options, std::string_view name, std::string_view value) {
  if (name == "Hash") {
    const auto parsed = parse_int(value);
    if (!parsed.has_value() || *parsed < 1 || *parsed > 1048576) {
      return false;
    }
    options.hash_mb = *parsed;
    return true;
  }

  if (name == "Threads") {
    const auto parsed = parse_int(value);
    if (!parsed.has_value() || *parsed != 1) {
      return false;
    }
    options.threads = *parsed;
    return true;
  }

  if (name == "Seed") {
    const auto parsed = parse_uint64(value);
    if (!parsed.has_value()) {
      return false;
    }
    options.seed = *parsed;
    return true;
  }

  return false;
}

} // namespace atropos::uci
