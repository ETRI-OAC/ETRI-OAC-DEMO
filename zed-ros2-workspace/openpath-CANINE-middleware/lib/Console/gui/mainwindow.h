#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include <QTableWidget>
#include <QTimer>
#include <QPen>

#include <iostream>
#include <unistd.h>

// gamepad
#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netinet/in.h>

#include "MotorDialog.h"
#include "CommunicationClient.h"
#include "IndexNotation.h"
#include "SharedMemory.h"
#include "qcustomplot.h"
#include "CAMEL_SDK/ENumClasses.hpp"

QT_BEGIN_NAMESPACE

namespace Ui
{
    class MainWindow;
}

QT_END_NAMESPACE


class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    MainWindow(QWidget* parent = nullptr);
    ~MainWindow();

    CommunicationClient* comm;
    QAction* actionMotorProtocol;
    QProgressBar* batteryProgressBar;

    // for middleware udp
    int sockfd;
    struct sockaddr_in servaddr;
    int middleware_update_flag;
    bool isFullScreenMode;

private Q_SLOTS:
    void onTcpConnected(QString ip);
    void onTcpDisconnected(QString ip, QString reason);
    void DisplayUpdate();
    void ReferenceUpdate();
    void scaleScreen();
    void SetToolBar();

    void on_BTN_EMERGENCY_STOP_clicked();
    void on_BTN_GDQ_START_clicked();
    void on_BTN_GDQ_READY_clicked();
    void on_BTN_GDQ_STAND_clicked();
    void on_BTN_GDQ_WALK_clicked();

protected:
    void mousePressEvent(QMouseEvent* event) override;

    void mouseMoveEvent(QMouseEvent* event) override;

    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    Ui::MainWindow* ui;
    MotorDialog* mMotorProtocol;
    void setupUdpIfNeeded(const QString& ip);
    void closeUdpIfActive(const char* reason = nullptr);


    QTimer* displayTimer;
    QTimer* udpTimer;
    bool mFSMDisplay = false;
    QPoint dragPosition; // 드래그 시작 위치
    bool dragging = false;


    int select_working;
    int lastSelected;

    void tcpSend();
    void ConnectionStatusDisplay();
    void updateStatusLED(bool currentValue, bool& prevValue, QLineEdit* targetWidget);
    void updateStatusIcon(bool currentValue, bool& prevValue, QAction* targetAction);
    void commandVelDisplay();
    void batteryDataDisplay();
    void fsmDisplay();

    FSM mPrevFSM;
};
#endif // MAINWINDOW_H
