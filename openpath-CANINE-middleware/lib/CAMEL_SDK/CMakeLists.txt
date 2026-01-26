cmake_minimum_required(VERSION 3.21)

find_package(Eigen3 REQUIRED)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

ADD_COMPILE_DEFINITIONS (LOG_DIR="${CMAKE_SOURCE_DIR}/log/")

message(STATUS "${ColorGreen}CAMEL SDK VERSION 1.16.1${ColorReset}")

add_library(CAMEL_SDK INTERFACE)

target_include_directories(CAMEL_SDK
        INTERFACE
        include
)

target_link_libraries(CAMEL_SDK INTERFACE
        Eigen3::Eigen
)

target_compile_definitions(CAMEL_SDK INTERFACE SIMUL=true)