cmake_minimum_required(VERSION 3.21)
project(OPENPATH-CANINE-MIDDLEWARE)

string(ASCII 27 Esc)
set(ColorBlue "${Esc}[34m")
set(ColorGreen "${Esc}[32m")
set(ColorRed "${Esc}[31m")
set(ColorReset "${Esc}[m")

function(print_option name value)
    if (${value})
        set(val "${ColorGreen}ON")
    else ()
        set(val "${ColorRed}OFF")
    endif ()
    message(STATUS "${ColorBlue}${name}:${ColorReset} ${val}${ColorReset}")
endfunction()

set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)

find_package(Eigen3 REQUIRED)
find_package(Qt5 REQUIRED COMPONENTS Core Network)

add_subdirectory(lib/CAMEL_SDK)
add_subdirectory(lib/Console)