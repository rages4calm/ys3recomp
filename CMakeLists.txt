cmake_minimum_required(VERSION 3.20)
project(ys3recomp VERSION 0.1.0 LANGUAGES CXX)

find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/toolchain.json" YS3_TOOLCHAIN)
string(JSON YS3_PINNED_REVISION GET "${YS3_TOOLCHAIN}" tool revision)
string(JSON YS3_RUNTIME_ABI GET "${YS3_TOOLCHAIN}" tool runtime_abi)
set(PCE_TOOL_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.deps/pcenginerecomp" CACHE PATH "Verified upstream source checkout")
set(PCE_EXPECTED_REVISION "${YS3_PINNED_REVISION}" CACHE STRING "Exact intended upstream revision; explicitly set when developing against a different commit")
get_filename_component(PCE_TOOL_ROOT "${PCE_TOOL_ROOT}" ABSOLUTE BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
execute_process(
  COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/verify_tool.py"
    --tool-root "${PCE_TOOL_ROOT}" --expected-revision "${PCE_EXPECTED_REVISION}"
    --expected-abi "${YS3_RUNTIME_ABI}"
  RESULT_VARIABLE YS3_VERIFY_RESULT OUTPUT_VARIABLE YS3_VERIFY_OUTPUT ERROR_VARIABLE YS3_VERIFY_ERROR)
if(NOT YS3_VERIFY_RESULT EQUAL 0)
  message(FATAL_ERROR "Upstream identity verification failed: ${YS3_VERIFY_ERROR}")
endif()
message(STATUS "${YS3_VERIFY_OUTPUT}")

include(CTest)
option(PCE_BUILD_DESKTOP "Build upstream optional SDL3 desktop host" OFF)
option(PCE_BUILD_REFERENCE_PROBE "Build upstream authored reference probes" OFF)
# The upstream owns the runtime, host, generated-module ABI and synthetic suites.
# All upstream-generated fixtures and binaries stay in a separate build directory.
add_subdirectory("${PCE_TOOL_ROOT}" "${CMAKE_CURRENT_BINARY_DIR}/upstream")
if(BUILD_TESTING)
  add_test(NAME consumer-contract
    COMMAND "${Python3_EXECUTABLE}" -m unittest discover -s tests -p "test_*.py" -v)
  set_tests_properties(consumer-contract PROPERTIES WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
endif()
