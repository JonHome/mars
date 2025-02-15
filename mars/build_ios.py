#!/usr/bin/env python3
import os
import sys
import glob
import shutil

from mars_utils import *


SCRIPT_PATH = os.path.split(os.path.realpath(__file__))[0]

BUILD_OUT_PATH = 'cmake_build/iOS'
INSTALL_PATH = BUILD_OUT_PATH + '/iOS.out'

IOS_BUILD_SIMULATOR_CMD = 'cmake ../.. -DCMAKE_BUILD_TYPE=Release ' \
                         '-DCMAKE_TOOLCHAIN_FILE=../../ios.toolchain.cmake ' \
                         '-DPLATFORM=SIMULATORARM64 ' \
                         '-DARCHS="arm64" ' \
                         '-DDEPLOYMENT_TARGET=16.4 ' \
                         '-DCMAKE_C_FLAGS="-mios-simulator-version-min=16.4" ' \
                         '-DCMAKE_CXX_FLAGS="-mios-simulator-version-min=16.4" ' \
                         '-DENABLE_ARC=0 ' \
                         '-DENABLE_BITCODE=0 ' \
                         '-DENABLE_VISIBILITY=1 && make -j8 && make install'
IOS_BUILD_OS_CMD = 'cmake ../.. -DCMAKE_BUILD_TYPE=Release ' \
                   '-DCMAKE_TOOLCHAIN_FILE=../../ios.toolchain.cmake ' \
                   '-DPLATFORM=OS64 ' \
                   '-DARCHS="arm64" ' \
                   '-DDEPLOYMENT_TARGET=16.4 ' \
                   '-DCMAKE_C_FLAGS="-mios-version-min=16.4" ' \
                   '-DCMAKE_CXX_FLAGS="-mios-version-min=16.4" ' \
                   '-DENABLE_ARC=0 ' \
                   '-DENABLE_BITCODE=0 ' \
                   '-DENABLE_VISIBILITY=1 && make -j8 && make install'

GEN_IOS_OS_PROJ = 'cmake ../.. -G Xcode ' \
                  '-DCMAKE_TOOLCHAIN_FILE=../../ios.toolchain.cmake ' \
                  '-DPLATFORM=OS64 ' \
                  '-DARCHS="arm64" ' \
                  '-DDEPLOYMENT_TARGET=16.4 ' \
                  '-DENABLE_ARC=0 ' \
                  '-DENABLE_BITCODE=0 ' \
                  '-DENABLE_VISIBILITY=1'
OPEN_SSL_ARCHS = ['arm64']


def build_ios(tag=''):
    gen_mars_revision_file('comm', tag)
    
    # 构建设备版本
    clean(BUILD_OUT_PATH)
    os.chdir(BUILD_OUT_PATH)
    ret = os.system(IOS_BUILD_OS_CMD)
    os.chdir(SCRIPT_PATH)
    if ret != 0:
        print('!!!!!!!!!!!build os fail!!!!!!!!!!!!!!!')
        return False

    libtool_os_dst_lib = INSTALL_PATH + '/os'
    libtool_src_lib = glob.glob(INSTALL_PATH + '/*.a')
    libtool_src_lib.append(BUILD_OUT_PATH + '/zstd/libzstd.a')
    if not libtool_libs(libtool_src_lib, libtool_os_dst_lib):
        return False

    # 构建模拟器版本
    clean(BUILD_OUT_PATH)
    os.chdir(BUILD_OUT_PATH)
    ret = os.system(IOS_BUILD_SIMULATOR_CMD)
    os.chdir(SCRIPT_PATH)
    if ret != 0:
        print('!!!!!!!!!!!build simulator fail!!!!!!!!!!!!!!!')
        return False
    
    libtool_simulator_dst_lib = INSTALL_PATH + '/simulator'
    if not libtool_libs(libtool_src_lib, libtool_simulator_dst_lib):
        return False

    # 使用新的合并函数
    lipo_dst_lib = INSTALL_PATH + '/mars'
    if not lipo_create_combined(libtool_os_dst_lib, libtool_simulator_dst_lib, lipo_dst_lib):
        return False

    # 处理 OpenSSL 库
    ssl_lib = INSTALL_PATH + '/ssl'
    if not lipo_thin_libs('openssl/openssl_lib_iOS/libssl.a', ssl_lib, OPEN_SSL_ARCHS):
        return False

    crypto_lib = INSTALL_PATH + '/crypto'
    if not lipo_thin_libs('openssl/openssl_lib_iOS/libcrypto.a', crypto_lib, OPEN_SSL_ARCHS):
        return False

    # 合并所有库
    final_libs = [lipo_dst_lib, ssl_lib, crypto_lib]
    final_dst_lib = INSTALL_PATH + '/mars_final'
    if not libtool_libs(final_libs, final_dst_lib):
        return False

    # 创建 framework
    dst_framework_path = INSTALL_PATH + '/mars.framework'
    make_static_framework(final_dst_lib, dst_framework_path, COMM_COPY_HEADER_FILES, '../')

    print('==================Output========================')
    print(dst_framework_path)
    return True

def build_ios_xlog(tag=''):
    gen_mars_revision_file('comm', tag)
    
    # 清理并创建输出目录
    if os.path.exists(INSTALL_PATH):
        shutil.rmtree(INSTALL_PATH)
    os.makedirs(INSTALL_PATH)
    
    # 构建设备版本
    clean(BUILD_OUT_PATH)
    os.chdir(BUILD_OUT_PATH)
    ret = os.system(IOS_BUILD_OS_CMD)
    os.chdir(SCRIPT_PATH)
    if ret != 0:
        print('!!!!!!!!!!!build os fail!!!!!!!!!!!!!!!')
        return False

    # 创建设备目录并合并库文件
    device_path = os.path.join(INSTALL_PATH, 'device')
    os.makedirs(device_path, exist_ok=True)
    
    device_lib = os.path.join(device_path, 'libmars.a')
    libtool_src_libs = [
        os.path.join(INSTALL_PATH, 'libcomm.a'),
        os.path.join(INSTALL_PATH, 'libmars-boost.a'),
        os.path.join(INSTALL_PATH, 'libxlog.a'),
        os.path.join(BUILD_OUT_PATH, 'zstd/libzstd.a')
    ]
    if not libtool_libs(libtool_src_libs, device_lib):
        return False

    # 创建设备 framework
    device_framework_path = os.path.join(device_path, 'mars.framework')
    if os.path.exists(device_framework_path):
        shutil.rmtree(device_framework_path)
    os.makedirs(device_framework_path)  # 确保 framework 目录存在
    
    # 复制二进制文件到 framework
    shutil.copy2(device_lib, os.path.join(device_framework_path, 'mars'))
    
    # 创建 Headers 目录并复制头文件
    headers_path = os.path.join(device_framework_path, 'Headers')
    os.makedirs(headers_path, exist_ok=True)
    for src, dst in XLOG_COPY_HEADER_FILES.items():
        header_dst = os.path.join(headers_path, dst)
        os.makedirs(header_dst, exist_ok=True)
        shutil.copy2(os.path.join('../', src), 
                    os.path.join(header_dst, os.path.basename(src)))

    print('!!!!!!!!!!!build os success!!!!!!!!!!!!!!!')

    # 构建模拟器版本
    clean(BUILD_OUT_PATH)
    os.chdir(BUILD_OUT_PATH)
    ret = os.system(IOS_BUILD_SIMULATOR_CMD)
    os.chdir(SCRIPT_PATH)
    if ret != 0:
        print('!!!!!!!!!!!build simulator fail!!!!!!!!!!!!!!!')
        return False
    

    # 创建模拟器目录并合并库文件
    simulator_path = os.path.join(INSTALL_PATH, 'simulator')
    os.makedirs(simulator_path, exist_ok=True)
    
    simulator_lib = os.path.join(simulator_path, 'libmars.a')
    if not libtool_libs(libtool_src_libs, simulator_lib):
        return False

    # 创建模拟器 framework
    simulator_framework_path = os.path.join(simulator_path, 'mars.framework')
    if os.path.exists(simulator_framework_path):
        shutil.rmtree(simulator_framework_path)
    os.makedirs(simulator_framework_path)  # 确保 framework 目录存在
    
    # 复制二进制文件到 framework
    shutil.copy2(simulator_lib, os.path.join(simulator_framework_path, 'mars'))
    
    # 创建 Headers 目录并复制头文件
    headers_path = os.path.join(simulator_framework_path, 'Headers')
    os.makedirs(headers_path, exist_ok=True)
    for src, dst in XLOG_COPY_HEADER_FILES.items():
        header_dst = os.path.join(headers_path, dst)
        os.makedirs(header_dst, exist_ok=True)
        shutil.copy2(os.path.join('../', src), 
                    os.path.join(header_dst, os.path.basename(src)))

    print('!!!!!!!!!!!build simulator success!!!!!!!!!!!!!!!')

    # 创建 XCFramework
    xcframework_path = os.path.join(INSTALL_PATH, 'mars.xcframework')
    print('!!!!!!!!!!!build 1')
    if os.path.exists(xcframework_path):
        shutil.rmtree(xcframework_path)
    print('!!!!!!!!!!!build 2')

    # 添加调试信息
    print(f'Checking device framework: {os.path.exists(device_framework_path)}')
    print(f'Checking device binary: {os.path.exists(os.path.join(device_framework_path, "mars"))}')
    print(f'Checking simulator framework: {os.path.exists(simulator_framework_path)}')
    print(f'Checking simulator binary: {os.path.exists(os.path.join(simulator_framework_path, "mars"))}')

    cmd = f'xcodebuild -create-xcframework ' \
          f'-framework {device_framework_path} ' \
          f'-framework {simulator_framework_path} ' \
          f'-output {xcframework_path}'
    
    print(f'Executing command: {cmd}')
    ret = os.system(cmd)
    print('!!!!!!!!!!!build 3')
    if ret != 0:
        print('!!!!!!!!!!!create xcframework fail!!!!!!!!!!!!!!!')
        return False
    print('!!!!!!!!!!!build 4')
    print('==================Output========================')
    print('XCFramework path: %s' % xcframework_path)
    return True



def gen_ios_project():
    gen_mars_revision_file('comm')
    clean(BUILD_OUT_PATH)
    os.chdir(BUILD_OUT_PATH)

    ret = os.system(GEN_IOS_OS_PROJ)
    os.chdir(SCRIPT_PATH)
    if ret != 0:
        print('!!!!!!!!!!!gen fail!!!!!!!!!!!!!!!')
        return False


    print('==================Output========================')
    print('project file: %s/%s' %(SCRIPT_PATH, BUILD_OUT_PATH))
    
    return True

def main():
    while True:
        if len(sys.argv) >= 2:
            build_ios(sys.argv[1])
            break
        else:
            num = input('Enter menu:\n1. Clean && build mars.\n2. Clean && build xlog.\n3. Gen iOS mars Project.\n4. Exit\n')
            if num == '1':
                build_ios()
                break
            if num == '2':
                build_ios_xlog()
                break
            elif num == '3':
                gen_ios_project()
                break
            elif num == '4':
                break
            else:
                build_ios()
                break

if __name__ == '__main__':
    main()
