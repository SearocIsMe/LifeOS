# The following lines of boilerplate have to be in your project's
# CMakeLists in this exact order for cmake to work correctly
cmake_minimum_required(VERSION 3.16)

# Force Ninja to write response (.rsp) files for every compile and link rule.
# The generated project_elf_src_<target>.c is compiled with the union of all
# component include directories, which can exceed the Windows command-line
# limit (32767 characters) and make CreateProcess fail. This must be set before
# project() so the Ninja generator picks it up.
if(CMAKE_GENERATOR MATCHES "Ninja")
    set(CMAKE_NINJA_FORCE_RESPONSE_FILE 1)
endif()

# Add this line to disable the specific warning
add_compile_options(-Wno-missing-field-initializers)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
# "Trim" the build. Include the minimal set of components, main, and anything it depends on.
idf_build_set_property(MINIMAL_BUILD ON)

set(PROJECT_VER "2.5.2")
project(xiaozhi)
