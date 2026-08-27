#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace atropos::uci {

struct EngineOptions {
  int hash_mb = 16;
  int threads = 1;
  std::uint64_t seed = 0;
};

struct UciOptionDescription {
  std::string name;
  std::string type;
  std::string default_value;
  std::optional<int> min;
  std::optional<int> max;
};

[[nodiscard]] std::vector<UciOptionDescription> describe_options();
[[nodiscard]] bool set_option(EngineOptions &options, std::string_view name,
                              std::string_view value);

} // namespace atropos::uci
