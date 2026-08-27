#include "transposition_table/transposition_table.hpp"

#include <algorithm>

namespace atropos::tt {
namespace {

[[nodiscard]] std::size_t entry_count_for_megabytes(int megabytes) {
  const int safe_megabytes = std::max(1, megabytes);
  const auto bytes = static_cast<std::size_t>(safe_megabytes) * 1024U * 1024U;
  return std::max<std::size_t>(1, bytes / sizeof(std::optional<Entry>));
}

} // namespace

TranspositionTable::TranspositionTable(int megabytes) { resize(megabytes); }

void TranspositionTable::resize(int megabytes) {
  entries_.assign(entry_count_for_megabytes(megabytes), std::nullopt);
}

void TranspositionTable::clear() {
  std::fill(entries_.begin(), entries_.end(), std::nullopt);
}

void TranspositionTable::store(Entry entry) {
  if (entries_.empty()) {
    return;
  }
  auto &slot = entries_[entry.key % entries_.size()];
  if (!slot.has_value() || entry.depth >= slot->depth || slot->key != entry.key) {
    slot = entry;
  }
}

std::optional<Entry> TranspositionTable::probe(std::uint64_t key) const {
  if (entries_.empty()) {
    return std::nullopt;
  }
  const auto &slot = entries_[key % entries_.size()];
  if (slot.has_value() && slot->key == key) {
    return slot;
  }
  return std::nullopt;
}

} // namespace atropos::tt
