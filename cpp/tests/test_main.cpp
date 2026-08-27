#include <exception>
#include <functional>
#include <iostream>
#include <string>
#include <vector>

namespace atropos::test {

struct Case {
  std::string name;
  std::function<void()> run;
};

std::vector<Case> &registry() {
  static std::vector<Case> cases;
  return cases;
}

void register_case(std::string name, std::function<void()> run) {
  registry().push_back({std::move(name), std::move(run)});
}

} // namespace atropos::test

int main() {
  int failures = 0;
  for (const auto &test : atropos::test::registry()) {
    try {
      test.run();
      std::cout << "[PASS] " << test.name << '\n';
    } catch (const std::exception &error) {
      ++failures;
      std::cerr << "[FAIL] " << test.name << ": " << error.what() << '\n';
    }
  }
  return failures == 0 ? 0 : 1;
}
