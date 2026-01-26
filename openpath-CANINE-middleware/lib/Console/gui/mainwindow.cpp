#include "mainwindow.h"
#include "./ui_mainwindow.h"

bool plot_OnOff = true;

extern pCAMEL_SHM sharedCamel;

MainWindow::MainWindow(QWidget* parent)
    : QMainWindow(parent)
      , ui(new Ui::MainWindow)
      , mPrevFSM(FSM_EMERGENCY_STOP)
{
    ui->setupUi(this);

    // initialization of shared memories

    SetToolBar();
    setWindowTitle("OPR-CANINE-MIDDLEWARE");
    setWindowFlags(Qt::FramelessWindowHint);
    QMainWindow::setWindowIcon(QIcon(QString(GUI_RSC_DIR) + "OPENPATH_ICON.png")); //TODO
    isFullScreenMode = false;
    // Dialog

    ui->LE_GDM_CMD->setStyleSheet("background-color:red");
    ui->LE_CONSOLE_CMD->setStyleSheet("background-color:red");

    lastSelected = J0;
    select_working = false;

    sockfd = -1;
    comm = new CommunicationClient(this);
    comm->setCandidateIps({ROBOT_ADDRESS, "127.0.0.1"});
    connect(comm, &CommunicationClient::tcpConnected, this, &MainWindow::onTcpConnected);
    connect(comm, &CommunicationClient::tcpDisconnected, this, &MainWindow::onTcpDisconnected);
    comm->startAutoConnect(1000); // 1초마다 연결 시도

    // rosComm = new ROSCommunication();

    ui->LE_ROBOT_STATE_2->setText("DISCONNECTED");
    ui->LE_CONNECT->setStyleSheet("background-color:red");
    ui->LE_SIT->setStyleSheet("background-color:red");
    ui->LE_STAND->setStyleSheet("background-color:red");
    ui->LE_WALK->setStyleSheet("background-color:red");
    displayTimer = new QTimer();
    connect(displayTimer, SIGNAL(timeout()), this, SLOT(DisplayUpdate()));
    displayTimer->start(100);

    // gamepad
    middleware_update_flag = false;

    // timer setting
    udpTimer = new QTimer();
    connect(udpTimer, SIGNAL(timeout()), this, SLOT(ReferenceUpdate())); // UDP(console -> controller)
    udpTimer->start(1);

#ifdef BUILD_STANDALONE
    scaleScreen();
#endif
}


void MainWindow::scaleScreen()
{
    if (isFullScreenMode)
    {
        isFullScreenMode = false;
        this->showNormal();
    }
    else
    {
        isFullScreenMode = true;
        this->showFullScreen();
    }
}

void MainWindow::onTcpConnected(QString ip)
{
    FILE_LOG(logINFO) << "[Main] TCP connected -> Setup UDP";
    setupUdpIfNeeded(ip);
}

void MainWindow::onTcpDisconnected(QString ip, QString reason)
{
    FILE_LOG(logWARNING) << "[Main] TCP disconnected (" << reason.toStdString() << ") -> Close UDP";
    closeUdpIfActive("TCP disconnected");
}

void MainWindow::setupUdpIfNeeded(const QString& ip)
{
    if (sockfd >= 0 && middleware_update_flag) return;

    if (sockfd >= 0) closeUdpIfActive("Recreate UDP");

    sockfd = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0)
    {
        FILE_LOG(logWARNING) << "[UDP] socket creation failed";
        middleware_update_flag = false;
        return;
    }

    std::memset(&servaddr, 0, sizeof(servaddr));
    servaddr.sin_family = AF_INET;
    servaddr.sin_port = htons(38335);
    if (::inet_pton(AF_INET, ip.toLocal8Bit().data(), &(servaddr.sin_addr)) != 1)
    {
        FILE_LOG(logWARNING) << "[UDP] inet_pton failed for " << ip.toStdString();
        closeUdpIfActive("inet_pton failed");
        return;
    }

    middleware_update_flag = true;
    FILE_LOG(logSUCCESS) << "[UDP] Ready to send to " << ip.toStdString() << ":38335";
}

void MainWindow::closeUdpIfActive(const char* reason)
{
    static bool closing = false;
    if (closing) return;
    closing = true;

    // 1) 송신 루프부터 멈추기 (다른 스레드가 바로 빠져나오게)
    middleware_update_flag = false;

    // 2) fd를 로컬로 복사하고, 공유 변수에서는 즉시 무효화
    int fd = sockfd;
    sockfd = -1;

    // 3) 실제 디스크립터를 닫기 (shutdown은 대기중인 I/O 깨우는 용도)
    if (fd >= 0)
    {
        ::shutdown(fd, SHUT_RDWR); // UDP에도 무해, 선택이지만 추천
        ::close(fd);
    }

    // 4) 상태 초기화
    std::memset(&servaddr, 0, sizeof(servaddr));
    FILE_LOG(logINFO) << "[UDP] Closed" << (reason ? std::string(" (") + reason + ")" : "");

    closing = false;
}

MainWindow::~MainWindow()
{
    delete ui;
    ui = NULL;
}

void MainWindow::ReferenceUpdate()
{
    LAN_MIDDLEWARE ros_data;

    if (middleware_update_flag)
    {
        ros_data.linearVelocityX = sharedCamel->ros2Data.baseRefVelX;
        ros_data.linearVelocityY = sharedCamel->ros2Data.baseRefVelY;
        ros_data.angularVelocityZ = sharedCamel->ros2Data.baseRefAngVelZ;
    }

    // udp joystick send //
    static int cnt;
    cnt++;
    if (cnt >= 50 && sockfd >= 0)
    {
        QByteArray SendData((char*)&ros_data, sizeof(LAN_MIDDLEWARE)); // 복사본 생성

        char header[2];
        header[0] = 0xFF;
        header[1] = 0xFE;

        char tail[2];
        tail[0] = 0x00;
        tail[1] = 0x01;

        SendData.prepend(header, 2);
        SendData.append(tail, 2);

        ::sendto(sockfd, SendData, SendData.size(), MSG_CONFIRM, (const struct sockaddr*)&servaddr, sizeof(servaddr));
        cnt = 0;
    }
}

void MainWindow::DisplayUpdate()
{
    tcpSend(); // TCP(console -> controller, command)
    ReferenceUpdate(); // UDP(console -> controller, ref vel.)
    // toolbar ==============================================================================
    ConnectionStatusDisplay();
    batteryDataDisplay();
    // sensor tab ===========================================================================
    commandVelDisplay();
    fsmDisplay();
}

void MainWindow::SetToolBar()
{
    actionMotorProtocol = new QAction(this);
    actionMotorProtocol->setCheckable(true);
    ui->mainToolBar->addAction(actionMotorProtocol);
    ui->mainToolBar->setIconSize(QSize(20, 20));
    //RobotInit
    {
        mMotorProtocol = new MotorDialog(this);
        QIcon iconRed(":/icons/power_button_red.png");
        QIcon iconGreen(":/icons/power_button_green.png");
        actionMotorProtocol->setIcon(sharedCamel->CAMEL_DATA_NEW.rawData.control_start == 1
                                         ? iconGreen
                                         : iconRed);
        QObject::connect(actionMotorProtocol, &QAction::toggled, [=]()
        {
            if (actionMotorProtocol->isChecked())
            {
                mMotorProtocol->setWindowFlags(Qt::Popup);
                QPoint pt(30, 10);
                pt = ui->centralwidget->mapToGlobal(pt);
                mMotorProtocol->move(pt);
                mMotorProtocol->show();
            }
        });
        QObject::connect(mMotorProtocol, &MotorDialog::SIG_ACTION_HIDE, actionMotorProtocol, &QAction::setChecked);
    }

    QWidget* spacer = new QWidget();
    spacer->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Preferred);
    ui->mainToolBar->addWidget(spacer);

    QWidget* centralWidget = new QWidget(this);
    QHBoxLayout* centralLayout = new QHBoxLayout(centralWidget);
    centralLayout->setContentsMargins(0, 0, 0, 0);
    centralLayout->setAlignment(Qt::AlignCenter);

    ui->mainToolBar->addWidget(centralWidget);
    QWidget* spacer3 = new QWidget();
    spacer3->setFixedWidth(60);
    spacer3->setSizePolicy(QSizePolicy::Fixed, QSizePolicy::Preferred);
    ui->mainToolBar->addWidget(spacer3);

    batteryProgressBar = new QProgressBar(this);
    batteryProgressBar->setMinimum(0);
    batteryProgressBar->setMaximum(100);
    batteryProgressBar->setValue(0);
    batteryProgressBar->setTextVisible(true);
    batteryProgressBar->setFormat("Robot : %p%");
    batteryProgressBar->setFixedSize(150, 20);
    ui->mainToolBar->addWidget(batteryProgressBar);

    QWidget* spacer2 = new QWidget();
    spacer2->setFixedWidth(20);
    ui->mainToolBar->addWidget(spacer2);
    QWidget* buttonContainer = new QWidget();
    QHBoxLayout* buttonLayout = new QHBoxLayout(buttonContainer);
    buttonLayout->setContentsMargins(0, 0, 0, 0);
    QPushButton* minimizeButton = new QPushButton("-");
    minimizeButton->setFixedSize(30, 30);
    minimizeButton->setStyleSheet("background-color: #ff9300");
    buttonLayout->addWidget(minimizeButton);
    QPushButton* maximizeButton = new QPushButton("□");
    maximizeButton->setFixedSize(30, 30);
    maximizeButton->setStyleSheet("background-color: #8ae234");
    buttonLayout->addWidget(maximizeButton);
    QPushButton* closeButton = new QPushButton("X");
    closeButton->setFixedSize(30, 30);
    closeButton->setStyleSheet("background-color: #ef2929   ");
    buttonLayout->addWidget(closeButton);
    ui->mainToolBar->addWidget(buttonContainer);
    connect(minimizeButton, &QPushButton::clicked, [&]() { this->showMinimized(); });
    connect(maximizeButton, &QPushButton::clicked, this, &MainWindow::scaleScreen);
    connect(closeButton, &QPushButton::clicked, [this]()
    {
        qApp->quit();
    });
}

void MainWindow::on_BTN_GDQ_START_clicked()
{
    COMMAND_STRUCT cmd;
    cmd.USER_COMMAND = CMD_CTRL_START;
    cmd.COMMAND_TARGET = CAMEL_CTRL;

    sharedCamel->COMMAND = cmd;
    sharedCamel->NEWCOMMAND = true;
}

void MainWindow::on_BTN_GDQ_READY_clicked()
{
    COMMAND_STRUCT cmd;
    cmd.USER_COMMAND = CMD_CTRL_READY;
    cmd.COMMAND_TARGET = CAMEL_CTRL;
    sharedCamel->COMMAND = cmd;
    sharedCamel->NEWCOMMAND = true;
}

void MainWindow::on_BTN_GDQ_STAND_clicked()
{
    COMMAND_STRUCT cmd;
    cmd.USER_COMMAND = CMD_CTRL_STAND;
    cmd.COMMAND_TARGET = CAMEL_CTRL;
    sharedCamel->COMMAND = cmd;
    sharedCamel->NEWCOMMAND = true;
}

void MainWindow::on_BTN_EMERGENCY_STOP_clicked()
{
    COMMAND_STRUCT cmd;
    cmd.USER_COMMAND = CMD_CTRL_E_STOP;
    cmd.COMMAND_TARGET = CAMEL_CTRL;
    sharedCamel->COMMAND = cmd;
    sharedCamel->NEWCOMMAND = true;
}

void MainWindow::on_BTN_GDQ_WALK_clicked()
{
    COMMAND_STRUCT cmd;
    cmd.USER_COMMAND = CMD_CTRL_WALK;
    cmd.COMMAND_TARGET = CAMEL_CTRL;
    sharedCamel->COMMAND = cmd;
    sharedCamel->NEWCOMMAND = true;
}


void MainWindow::tcpSend()
{
    if (!sharedCamel->NEWCOMMAND) return;
    sharedCamel->NEWCOMMAND = false;

    // 구조체를 바로 보내기
    if (!comm->sendCommand(sharedCamel->COMMAND))
    {
        FILE_LOG(logWARNING) << "[Main] tcpSend failed (not connected)";
    }
}

void MainWindow::ConnectionStatusDisplay()
{
    static bool bPrevRobotConnection = false;
    static bool bPrevMotorControlStart = false;
    static bool bPrevROSConnected = false;
    static bool bPrevHarnessMode = false;
    static bool bPrevTurboMode = false;
    static bool bPrevVisionMode = false;
    static bool bPrevGDMControlled = false;
    static bool bPrevConsoleControlled = false;
    // LAN 및 CAMEL 연결 상태 확인
    bool bRobotConnected = sharedCamel->bIsConnect;

    if (bPrevRobotConnection != bRobotConnected)
    {
        if (!bPrevRobotConnection)
        {
            ui->LE_CONNECT->setStyleSheet("background-color:lightgreen");
            mFSMDisplay = true;
        }
        else
        {
            ui->LE_CONNECT->setStyleSheet("background-color:red");
            ui->LE_ROBOT_STATE_2->setText("DISCONNECTED");
            updateStatusIcon(false, bPrevMotorControlStart, actionMotorProtocol);
            updateStatusLED(false, bPrevConsoleControlled, ui->LE_CONSOLE_CMD);
            updateStatusLED(false, bPrevGDMControlled, ui->LE_GDM_CMD);
            ui->LE_SIT->setStyleSheet("background-color:red");
            ui->LE_STAND->setStyleSheet("background-color:red");
            ui->LE_WALK->setStyleSheet("background-color:red");
        }
        bPrevRobotConnection = bRobotConnected;
    }
    if (bRobotConnected)
    {
        updateStatusIcon(sharedCamel->CAMEL_DATA_NEW.rawData.control_start, bPrevMotorControlStart,
                         actionMotorProtocol);
        updateStatusLED(sharedCamel->CAMEL_DATA_NEW.bConsoleCommand, bPrevConsoleControlled, ui->LE_CONSOLE_CMD);
        // updateStatusLED(sharedCamel->CAMEL_DATA_NEW.bGDMCommand, bPrevGDMControlled, ui->LE_GDM_CMD);

        if (sharedCamel->ros2Data.isConnected)
        {
            ui->LE_GDM_CMD->setStyleSheet("background-color:lightgreen");
        }
        else
        {
            ui->LE_GDM_CMD->setStyleSheet("background-color:red");
        }
    }
}

void MainWindow::updateStatusLED(bool currentValue, bool& prevValue, QLineEdit* targetWidget)
{
    if (currentValue != prevValue)
    {
        targetWidget->setStyleSheet(currentValue ? "background-color:lightgreen" : "background-color:red");
        prevValue = currentValue;
    }
}

void MainWindow::updateStatusIcon(bool currentValue, bool& prevValue, QAction* targetAction)
{
    // 아이콘 파일 설정
    QIcon iconRed(":/icons/power_button_red.png");
    QIcon iconGreen(":/icons/power_button_green.png");
    if (currentValue != prevValue)
    {
        targetAction->setIcon(currentValue ? iconGreen : iconRed);
        prevValue = currentValue;
    }
}

void MainWindow::commandVelDisplay()
{
    Eigen::Vector3d act_vel = sharedCamel->CAMEL_DATA_NEW.actual_vel;
    Eigen::Vector3d cmd_vel = sharedCamel->CAMEL_DATA_NEW.cmd_vel;
    ui->TW_VELOCITY->setItem(0, 0, new
                             QTableWidgetItem(QString::number(cmd_vel(0), 'f', 2)));
    ui->TW_VELOCITY->setItem(0, 1, new
                             QTableWidgetItem(QString::number(cmd_vel(1), 'f', 2)));
    ui->TW_VELOCITY->setItem(0, 2, new
                             QTableWidgetItem(QString::number(cmd_vel(2), 'f', 2)));
    ui->TW_VELOCITY->setItem(1, 0, new
                             QTableWidgetItem(QString::number(act_vel(0), 'f', 2)));
    ui->TW_VELOCITY->setItem(1, 1, new
                             QTableWidgetItem(QString::number(act_vel(1), 'f', 2)));
    ui->TW_VELOCITY->setItem(1, 2, new
                             QTableWidgetItem(QString::number(act_vel(2), 'f', 2)));
}

void MainWindow::batteryDataDisplay()
{
    int batterypercentage = int((sharedCamel->CAMEL_DATA_NEW.rawData.battery_voltage - 42.0) / (52.6 - 42.0) * 100);
    batterypercentage = std::clamp(batterypercentage, 0, 100);
    batteryProgressBar->setValue(batterypercentage);
    batteryProgressBar->setFormat("Robot : " + QString::number(batterypercentage, 'f', 1) + "%");
}

void MainWindow::fsmDisplay()
{
    static FSM prevFSM;
    if (prevFSM != sharedCamel->CAMEL_DATA_NEW.fsm_state)
    {
        mFSMDisplay = true;
        prevFSM = sharedCamel->CAMEL_DATA_NEW.fsm_state;
    }
    if (mFSMDisplay)
    {
        mFSMDisplay = false;
        switch (sharedCamel->CAMEL_DATA_NEW.fsm_state)
        {
        case FSM_INITIAL:
            ui->LE_ROBOT_STATE_2->setText("INITIAL");
            ui->BTN_GDQ_START->setEnabled(true);
            ui->BTN_GDQ_STAND->setDisabled(true);
            ui->BTN_GDQ_READY->setDisabled(true);
            ui->BTN_GDQ_WALK->setDisabled(true);

            ui->LE_SIT->setStyleSheet("background-color:red");
            ui->LE_STAND->setStyleSheet("background-color:red");
            ui->LE_WALK->setStyleSheet("background-color:red");
            break;
        case FSM_INITIALIZING:
            ui->LE_ROBOT_STATE_2->setText("INITIALIZING...");
            ui->BTN_GDQ_START->setEnabled(true);
            ui->BTN_GDQ_STAND->setDisabled(true);
            ui->BTN_GDQ_READY->setDisabled(true);
            ui->BTN_GDQ_WALK->setDisabled(true);

            ui->LE_SIT->setStyleSheet("background-color:red");
            ui->LE_STAND->setStyleSheet("background-color:red");
            ui->LE_WALK->setStyleSheet("background-color:red");
            break;
        case FSM_EMERGENCY_STOP:
            ui->LE_ROBOT_STATE_2->setText("E-STOP");
            ui->BTN_GDQ_START->setEnabled(true);
            ui->BTN_GDQ_STAND->setDisabled(true);
            ui->BTN_GDQ_READY->setDisabled(true);
            ui->BTN_GDQ_WALK->setDisabled(true);

            ui->LE_SIT->setStyleSheet("background-color:red");
            ui->LE_STAND->setStyleSheet("background-color:red");
            ui->LE_WALK->setStyleSheet("background-color:red");
            break;
        case FSM_READY:
            ui->LE_ROBOT_STATE_2->setText("READY");
            ui->BTN_GDQ_START->setDisabled(true);
            ui->BTN_GDQ_STAND->setEnabled(true);
            ui->BTN_GDQ_READY->setDisabled(true);
            ui->BTN_GDQ_WALK->setDisabled(true);

            ui->LE_SIT->setStyleSheet("background-color:lightgreen");
            ui->LE_STAND->setStyleSheet("background-color:red");
            ui->LE_WALK->setStyleSheet("background-color:red");
            if (sharedCamel->ros2Data.bNewCommand)
            {
                FILE_LOG(logINFO) << "[ROS2] Received ROS Command : " << sharedCamel->ros2Data.command;
                sharedCamel->ros2Data.bNewCommand = false;
                switch (sharedCamel->ros2Data.command)
                {
                case CMD_ROS_STAND:
                    {
                        on_BTN_GDQ_STAND_clicked();
                        break;
                    }
                default:
                    break;
                }
            }
            break;
        case FSM_STAND_UP:
            ui->LE_ROBOT_STATE_2->setText("STAND-UP");
            ui->BTN_GDQ_START->setDisabled(true);
            ui->BTN_GDQ_STAND->setDisabled(true);
            ui->BTN_GDQ_READY->setDisabled(true);
            ui->BTN_GDQ_WALK->setDisabled(true);

            ui->LE_SIT->setStyleSheet("background-color:red");
            ui->LE_STAND->setStyleSheet("background-color:lightgreen");
            ui->LE_WALK->setStyleSheet("background-color:red");
            break;
        case FSM_SIT_DOWN:
            ui->LE_ROBOT_STATE_2->setText("SIT-DOWN");
            ui->BTN_GDQ_START->setDisabled(true);
            ui->BTN_GDQ_STAND->setDisabled(true);
            ui->BTN_GDQ_READY->setDisabled(true);
            ui->BTN_GDQ_WALK->setDisabled(true);

            ui->LE_SIT->setStyleSheet("background-color:lightgreen");
            ui->LE_STAND->setStyleSheet("background-color:red");
            ui->LE_WALK->setStyleSheet("background-color:red");
            break;
        case FSM_STAND:
            ui->LE_ROBOT_STATE_2->setText("STAND");
            ui->BTN_GDQ_START->setDisabled(true);
            ui->BTN_GDQ_STAND->setDisabled(true);
            ui->BTN_GDQ_READY->setEnabled(true);
            ui->BTN_GDQ_WALK->setEnabled(true);

            ui->LE_SIT->setStyleSheet("background-color:red");
            ui->LE_STAND->setStyleSheet("background-color:lightgreen");
            ui->LE_WALK->setStyleSheet("background-color:red");
            break;
        case FSM_TROT_STOP:
            ui->LE_ROBOT_STATE_2->setText("STOPPING");
            ui->BTN_GDQ_START->setDisabled(true);
            ui->BTN_GDQ_STAND->setEnabled(true);
            ui->BTN_GDQ_READY->setDisabled(true);
            ui->BTN_GDQ_WALK->setDisabled(true);
            break;
        case FSM_WALK:
            ui->LE_ROBOT_STATE_2->setText("WALK");
            ui->BTN_GDQ_START->setDisabled(true);
            ui->BTN_GDQ_STAND->setEnabled(true);
            ui->BTN_GDQ_READY->setEnabled(true);
            ui->BTN_GDQ_WALK->setDisabled(true);

            ui->LE_SIT->setStyleSheet("background-color:red");
            ui->LE_STAND->setStyleSheet("background-color:red");
            ui->LE_WALK->setStyleSheet("background-color:lightgreen");
            break;
        case FSM_STAIR:
            ui->LE_ROBOT_STATE_2->setText("STAIR");
            ui->BTN_GDQ_START->setDisabled(true);
            ui->BTN_GDQ_STAND->setEnabled(true);
            ui->BTN_GDQ_READY->setEnabled(true);
            ui->BTN_GDQ_WALK->setEnabled(true);

            ui->LE_SIT->setStyleSheet("background-color:red");
            ui->LE_STAND->setStyleSheet("background-color:red");
            ui->LE_WALK->setStyleSheet("background-color:red");
            break;
        case FSM_RLWALK:
            ui->LE_ROBOT_STATE_2->setText("RL WALK");
            ui->BTN_GDQ_START->setDisabled(true);
            ui->BTN_GDQ_STAND->setEnabled(true);
            ui->BTN_GDQ_READY->setEnabled(true);
            ui->BTN_GDQ_WALK->setEnabled(true);

            ui->LE_SIT->setStyleSheet("background-color:red");
            ui->LE_STAND->setStyleSheet("background-color:red");
            ui->LE_WALK->setStyleSheet("background-color:red");
            break;
        case FSM_PRONKING:
            ui->LE_ROBOT_STATE_2->setText("PRONKING");
            ui->BTN_GDQ_START->setDisabled(true);
            ui->BTN_GDQ_STAND->setEnabled(true);
            ui->BTN_GDQ_READY->setEnabled(true);
            ui->BTN_GDQ_WALK->setEnabled(true);

            ui->LE_SIT->setStyleSheet("background-color:red");
            ui->LE_STAND->setStyleSheet("background-color:red");
            ui->LE_WALK->setStyleSheet("background-color:red");
            break;
        case FSM_BOUNDING:
            ui->LE_ROBOT_STATE_2->setText("BOUNDING");
            ui->BTN_GDQ_START->setDisabled(true);
            ui->BTN_GDQ_STAND->setEnabled(true);
            ui->BTN_GDQ_READY->setEnabled(true);
            ui->BTN_GDQ_WALK->setEnabled(true);

            ui->LE_SIT->setStyleSheet("background-color:red");
            ui->LE_STAND->setStyleSheet("background-color:red");
            ui->LE_WALK->setStyleSheet("background-color:red");
            break;
        case FSM_PACING:
            ui->LE_ROBOT_STATE_2->setText("PACING");
            ui->BTN_GDQ_START->setDisabled(true);
            ui->BTN_GDQ_STAND->setEnabled(true);
            ui->BTN_GDQ_READY->setEnabled(true);
            ui->BTN_GDQ_WALK->setEnabled(true);

            ui->LE_SIT->setStyleSheet("background-color:red");
            ui->LE_STAND->setStyleSheet("background-color:red");
            ui->LE_WALK->setStyleSheet("background-color:red");
            break;
        case FSM_RECOVERY:
            ui->LE_ROBOT_STATE_2->setText("RECOVERY");
            break;
        default:
            ui->LE_ROBOT_STATE_2->setText("ERROR");
            break;
        }
    }


    switch (sharedCamel->CAMEL_DATA_NEW.fsm_state)
    {
    case FSM_INITIAL:
        if (sharedCamel->ros2Data.bNewCommand)
        {
            FILE_LOG(logINFO) << "[ROS2] Received ROS Command : " << sharedCamel->ros2Data.command;
            sharedCamel->ros2Data.bNewCommand = false;
            switch (sharedCamel->ros2Data.command)
            {
            case CMD_ROS_START:
                {
                    on_BTN_GDQ_START_clicked();
                    break;
                }
            default:
                break;
            }
        }

        break;
    case FSM_INITIALIZING:
        break;
    case FSM_EMERGENCY_STOP:
        break;
    case FSM_READY:
        if (sharedCamel->ros2Data.bNewCommand)
        {
            FILE_LOG(logINFO) << "[ROS2] Received ROS Command : " << sharedCamel->ros2Data.command;
            sharedCamel->ros2Data.bNewCommand = false;
            switch (sharedCamel->ros2Data.command)
            {
            case CMD_ROS_STAND:
                {
                    on_BTN_GDQ_STAND_clicked();
                    break;
                }
            default:
                break;
            }
        }
        break;
    case FSM_STAND_UP:
        break;
    case FSM_SIT_DOWN:
        break;
    case FSM_STAND:
        if (sharedCamel->ros2Data.bNewCommand)
        {
            FILE_LOG(logINFO) << "[ROS2] Received ROS Command : " << sharedCamel->ros2Data.command;
            sharedCamel->ros2Data.bNewCommand = false;
            switch (sharedCamel->ros2Data.command)
            {
            case CMD_ROS_READY:
                {
                    on_BTN_GDQ_READY_clicked();
                    break;
                }
            case CMD_ROS_WALK:
                {
                    on_BTN_GDQ_WALK_clicked();
                    break;
                }
            default:
                break;
            }
        }
        break;
    case FSM_TROT_STOP:
        break;
    case FSM_WALK:
        if (sharedCamel->ros2Data.bNewCommand)
        {
            FILE_LOG(logINFO) << "[ROS2] Received ROS Command : " << sharedCamel->ros2Data.command;
            sharedCamel->ros2Data.bNewCommand = false;
            switch (sharedCamel->ros2Data.command)
            {
            case CMD_ROS_STAND:
                {
                    on_BTN_GDQ_STAND_clicked();
                    break;
                }
            case CMD_ROS_READY:
                {
                    on_BTN_GDQ_READY_clicked();
                    break;
                }
            default:
                break;
            }
        }
        break;
    case FSM_STAIR:
        break;
    case FSM_RLWALK:
        break;
    case FSM_PRONKING:
        break;
    case FSM_BOUNDING:
        break;
    case FSM_PACING:
        break;
    case FSM_RECOVERY:
        break;
    default:
        break;
    }
}

void MainWindow::mousePressEvent(QMouseEvent* event)
{
    if (ui->mainToolBar->geometry().contains(event->pos()) && event->button() == Qt::LeftButton)
    {
        dragPosition = event->globalPos() - frameGeometry().topLeft();
        dragging = true;
        event->accept();
    }
}

void MainWindow::mouseMoveEvent(QMouseEvent* event)
{
    if (dragging && (event->buttons() & Qt::LeftButton))
    {
        move(event->globalPos() - dragPosition);
        event->accept();
    }
}

void MainWindow::mouseReleaseEvent(QMouseEvent* event)
{
    if (event->button() == Qt::LeftButton)
    {
        dragging = false;
        event->accept();
    }
}
