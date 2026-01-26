#include "gui/mainwindow.h"
#include "ROSCommunication.hpp"
#include <QApplication>

std::string AL_NAME = "CAMEL-GUI";
pCAMEL_SHM sharedCamel;

int main(int argc, char *argv[])
{
    // 0) shared memory 초기화
    sharedCamel = new CAMEL_SHM();

    // 1) ROS context를 먼저 초기화 (Qt가 argv를 건드리기 전에)
    auto context = std::make_shared<rclcpp::Context>();
    context->init(argc, argv);

    // 2) Qt 애플리케이션 생성
    QApplication app(argc, argv);

    // 3) 동일 컨텍스트로 노드 생성
    rclcpp::NodeOptions node_opts;
    node_opts.context(context);
    auto node = std::make_shared<ROSCommunication>(node_opts);

    // 4) 동일 컨텍스트로 Executor 만들고, 스핀은 별도 스레드에서
    rclcpp::ExecutorOptions exec_opts;
    exec_opts.context = context;
    rclcpp::executors::MultiThreadedExecutor exec(exec_opts);
    exec.add_node(node);

    std::thread spin_thread([&exec](){
      exec.spin();  // 블록 (백그라운드에서 콜백 수행)
    });

    // 5) Qt GUI 띄우기 (필요시 node를 주입)
    MainWindow w;
    w.show();

    // 6) Qt 종료 시 ROS도 안전하게 정리
    QObject::connect(&app, &QCoreApplication::aboutToQuit, [&](){
      exec.cancel();                 // 스핀 멈추기
    });

    int rc = app.exec();
    exec.cancel();
    if (spin_thread.joinable()) spin_thread.join();
    node.reset();                    // ROS 객체 먼저 파괴
    rclcpp::shutdown(context);       // 마지막에 shutdown
    return rc;
}