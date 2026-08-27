if(NOT DEFINED ATROPOS_BIN)
  message(FATAL_ERROR "ATROPOS_BIN is required")
endif()

set(input_file "${CMAKE_CURRENT_LIST_DIR}/../tests/fixtures/phase0/uci_smoke.in")
execute_process(
  COMMAND "${ATROPOS_BIN}"
  INPUT_FILE "${input_file}"
  OUTPUT_VARIABLE uci_stdout
  ERROR_VARIABLE uci_stderr
  RESULT_VARIABLE result
  TIMEOUT 5
)

if(NOT result EQUAL 0)
  message(FATAL_ERROR "UCI smoke process failed: ${result}\nstderr:\n${uci_stderr}")
endif()

foreach(required_line IN ITEMS "id name Atropos" "uciok" "readyok" "bestmove ")
  string(FIND "${uci_stdout}" "${required_line}" found_at)
  if(found_at EQUAL -1)
    message(FATAL_ERROR "UCI smoke missing '${required_line}' in stdout:\n${uci_stdout}")
  endif()
endforeach()

if(NOT "${uci_stderr}" STREQUAL "")
  message(FATAL_ERROR "UCI smoke emitted unexpected stderr:\n${uci_stderr}")
endif()
