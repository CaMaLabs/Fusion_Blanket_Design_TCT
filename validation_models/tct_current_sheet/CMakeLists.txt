cmake_minimum_required(VERSION 3.13)

project(tct-current-sheet LANGUAGES CXX)

if(NOT TARGET bout++::bout++)
  find_package(bout++ REQUIRED)
endif()

add_executable(tct_current_sheet tct_current_sheet.cxx)
target_link_libraries(tct_current_sheet PRIVATE bout++::bout++)
