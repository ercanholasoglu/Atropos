cmake_minimum_required(VERSION 3.24)

project(
  Atropos
  VERSION 0.0.1
  DESCRIPTION "Research-grade UCI chess engine"
  LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(ATROPOS_ENABLE_WARNINGS_AS_ERRORS "Treat compiler warnings as errors" ON)

add_library(atropos_core
  src/benchmark/bench.cpp
  src/board/state.cpp
  src/board/types.cpp
  src/evaluation/evaluate.cpp
  src/movegen/movegen.cpp
  src/perft/perft.cpp
  src/search/search.cpp
  src/strength/gauntlet.cpp
  src/strength/selfplay.cpp
  src/transposition_table/transposition_table.cpp
  src/uci/command.cpp
  src/uci/engine.cpp
  src/uci/options.cpp
  src/zobrist/zobrist.cpp
)

target_include_directories(atropos_core PUBLIC src)

target_compile_options(atropos_core PRIVATE
  -Wall -Wextra -Wpedantic -Wconversion -Wshadow
  $<$<BOOL:${ATROPOS_ENABLE_WARNINGS_AS_ERRORS}>:-Werror>
)

add_executable(atropos src/main.cpp)
target_link_libraries(atropos PRIVATE atropos_core)
target_compile_options(atropos PRIVATE
  -Wall -Wextra -Wpedantic -Wconversion -Wshadow
  $<$<BOOL:${ATROPOS_ENABLE_WARNINGS_AS_ERRORS}>:-Werror>
)

enable_testing()

add_executable(atropos_tests
  tests/test_main.cpp
  tests/benchmark_test.cpp
  tests/board_state_test.cpp
  tests/evaluation_test.cpp
  tests/movegen_test.cpp
  tests/perft_test.cpp
  tests/search_test.cpp
  tests/gauntlet_test.cpp
  tests/selfplay_test.cpp
  tests/transposition_table_test.cpp
  tests/tactical_suite_test.cpp
  tests/uci_command_test.cpp
  tests/uci_engine_test.cpp
)
target_link_libraries(atropos_tests PRIVATE atropos_core)
target_compile_options(atropos_tests PRIVATE
  -Wall -Wextra -Wpedantic -Wconversion -Wshadow
  $<$<BOOL:${ATROPOS_ENABLE_WARNINGS_AS_ERRORS}>:-Werror>
)

add_test(NAME atropos_unit COMMAND atropos_tests)
set_tests_properties(atropos_unit PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

add_test(
  NAME atropos_uci_smoke
  COMMAND ${CMAKE_COMMAND}
    -DATROPOS_BIN=$<TARGET_FILE:atropos>
    -P ${CMAKE_CURRENT_SOURCE_DIR}/cmake/uci_smoke.cmake
)

find_program(CLANG_FORMAT_EXE clang-format)
if(CLANG_FORMAT_EXE)
  file(GLOB_RECURSE ATROPOS_FORMAT_FILES CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/*.hpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/*.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/*.hpp")
  add_custom_target(format
    COMMAND ${CLANG_FORMAT_EXE} -i ${ATROPOS_FORMAT_FILES}
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
  add_custom_target(format-check
    COMMAND ${CLANG_FORMAT_EXE} --dry-run --Werror ${ATROPOS_FORMAT_FILES}
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
else()
  add_custom_target(format-check
    COMMAND ${CMAKE_COMMAND} -E echo "clang-format not found - format-check skipped")
endif()

find_program(CLANG_TIDY_EXE clang-tidy)
if(CLANG_TIDY_EXE)
  add_custom_target(lint
    COMMAND ${CLANG_TIDY_EXE}
      -p ${CMAKE_BINARY_DIR}
      ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp
      ${CMAKE_CURRENT_SOURCE_DIR}/src/benchmark/bench.cpp
      ${CMAKE_CURRENT_SOURCE_DIR}/src/board/state.cpp
      ${CMAKE_CURRENT_SOURCE_DIR}/src/board/types.cpp
      ${CMAKE_CURRENT_SOURCE_DIR}/src/evaluation/evaluate.cpp
      ${CMAKE_CURRENT_SOURCE_DIR}/src/movegen/movegen.cpp
      ${CMAKE_CURRENT_SOURCE_DIR}/src/perft/perft.cpp
      ${CMAKE_CURRENT_SOURCE_DIR}/src/search/search.cpp
      ${CMAKE_CURRENT_SOURCE_DIR}/src/strength/gauntlet.cpp
      ${CMAKE_CURRENT_SOURCE_DIR}/src/strength/selfplay.cpp
      ${CMAKE_CURRENT_SOURCE_DIR}/src/transposition_table/transposition_table.cpp
      ${CMAKE_CURRENT_SOURCE_DIR}/src/uci/command.cpp
      ${CMAKE_CURRENT_SOURCE_DIR}/src/uci/engine.cpp
      ${CMAKE_CURRENT_SOURCE_DIR}/src/uci/options.cpp
      ${CMAKE_CURRENT_SOURCE_DIR}/src/zobrist/zobrist.cpp
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
else()
  add_custom_target(lint
    COMMAND ${CMAKE_COMMAND} -E echo "clang-tidy not found - lint skipped")
endif()
