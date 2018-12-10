cmake_minimum_required(VERSION 3.12)
project(TRexServer)

set(CMAKE_CXX_STANDARD 14)

include_directories(.)
include_directories(TRex-Server)
include_directories(TRex-Server/src)
include_directories(TRex-Server/src/Connection)
include_directories(TRex-Server/src/Packet)
include_directories(TRex-Server/src/Server)
include_directories(TRex-Server/src/Test)
include_directories(TRex-Server/src/Util)
include_directories(TRex2-lib)
include_directories(TRex2-lib/src/Common)
include_directories(TRex2-lib/src/Communication)
include_directories(TRex2-lib/src/Engine)
include_directories(TRex2-lib/src/Engine/GPU)
include_directories(TRex2-lib/src/Marshalling)
include_directories(TRex2-lib/src/Packets)

# This custom target builds the entire T-Rex project in order to run TRex-Server/src/TRexServer.
# Before building TRex-Server, we must build TRex2-lib. However, because of how the TRex-Server Makefile is set up,
# it will always rebuild the link with TRex2-lib when the library has been changed, i.e., make install is executed in
# TRex2-lib. To prevent this, we will only run make install in TRex2-lib if a source file has changed in TRex2-lib,
# or, the output from running "make" is not "Nothing to be done for 'all'.
add_custom_target(TRexServer COMMAND ${PROJECT_SOURCE_DIR}/TRex/TRex-Server/custom_setup.sh
        CLION_EXE_DIR=${PROJECT_SOURCE_DIR}/TRex/TRex-Server/src)

add_custom_target(ConfigureDebugTRex COMMAND ${PROJECT_SOURCE_DIR}/TRex/TRex2-lib/run_debug_configure && ${PROJECT_SOURCE_DIR}/TRex/TRex-Server/run_debug_configure
        CLION_EXE_DIR=${PROJECT_SOURCE_DIR}/TRex/TRex-Server/src)

add_custom_target(ConfigureProdTRex COMMAND ${PROJECT_SOURCE_DIR}/TRex/TRex2-lib/run_production_configure && ${PROJECT_SOURCE_DIR}/TRex/TRex-Server/run_production_configure
        CLION_EXE_DIR=${PROJECT_SOURCE_DIR}/TRex/TRex-Server/src)
