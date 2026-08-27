#pragma once

#include <functional>
#include <stdexcept>
#include <string>

namespace atropos::test {

void register_case(std::string name, std::function<void()> run);

struct Registrar {
  Registrar(std::string name, std::function<void()> run) { register_case(std::move(name), std::move(run)); }
};

} // namespace atropos::test

#define ATROPOS_CONCAT_INNER(a, b) a##b
#define ATROPOS_CONCAT(a, b) ATROPOS_CONCAT_INNER(a, b)

#define TEST_CASE(name)                                                                            \
  static void ATROPOS_CONCAT(test_, __LINE__)();                                                    \
  static ::atropos::test::Registrar ATROPOS_CONCAT(registrar_, __LINE__)(name,                      \
                                                                          ATROPOS_CONCAT(test_, __LINE__)); \
  static void ATROPOS_CONCAT(test_, __LINE__)()

#define REQUIRE(condition)                                                                          \
  do {                                                                                              \
    if (!(condition)) {                                                                             \
      throw std::runtime_error(std::string("requirement failed: ") + #condition);                  \
    }                                                                                               \
  } while (false)

#define REQUIRE_EQ(left, right)                                                                     \
  do {                                                                                              \
    const auto &actual_value = (left);                                                              \
    const auto &expected_value = (right);                                                           \
    if (!(actual_value == expected_value)) {                                                        \
      throw std::runtime_error(std::string("requirement failed: ") + #left + " == " + #right);    \
    }                                                                                               \
  } while (false)
