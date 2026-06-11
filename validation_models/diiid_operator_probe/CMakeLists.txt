cmake_minimum_required(VERSION 3.13)

project(diiid-operator-probe LANGUAGES CXX)

if(NOT TARGET bout++::bout++)
  find_package(bout++ REQUIRED)
endif()

add_executable(diiid_operator_probe diiid_operator_probe.cxx)
target_link_libraries(diiid_operator_probe PRIVATE bout++::bout++)
