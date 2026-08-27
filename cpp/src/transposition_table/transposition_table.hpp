#pragma once

#include "board/types.hpp"

#include <cstddef>
#include <cstdint>
#include <optional>
#include <vector>

namespace atropos::tt {

enum class Bound : std::uint8_t { Exact, Lower, Upper };

struct Entry {
  std::uint64_t key = 0;
  int depth = 0;
  int score = 0;
  Bound bound = Bound::Exact;
  std::optional<board::Move> best_move;
};

class TranspositionTable {
public:
  explicit TranspositionTable(int megabytes = 16);

  void resize(int megabytes);
  void clear();
  void store(Entry entry);

  [[nodiscard]] std::optional<Entry> probe(std::uint64_t key) const;
  [[nodiscard]] std::size_t capacity() const noexcept { return entries_.size(); }

private:
  std::vector<std::optional<Entry>> entries_;
};

} // namespace atropos::tt
