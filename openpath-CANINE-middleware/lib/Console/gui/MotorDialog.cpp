#include "MotorDialog.h"
#include "./ui_MotorDialog.h"

#include <QDebug>

#include "CAMEL_SDK/CAMEL_api.hpp"

#include "SharedMemory.h"
#include "IndexNotation.h"

MotorDialog::MotorDialog(QWidget *parent) : QDialog(parent), m_ui(new Ui::MotorDialog)
{
    m_ui->setupUi(this);
    m_updateTimer = new QTimer();
    QObject::connect(m_updateTimer, &QTimer::timeout, this, &MotorDialog::update);
    m_updateTimer->start(500);
}

MotorDialog::~MotorDialog()
{
    delete m_ui;
    m_ui = NULL;
}

void MotorDialog::update()
{
    /// Auto Start Status
    if (sharedCamel->CAMEL_DATA_NEW.rawData.can_check == 0)
        m_ui->LE_CAN_CHECK_STATUS->setStyleSheet(
            "background-color:red");
    if (sharedCamel->CAMEL_DATA_NEW.rawData.can_check == 1)
        m_ui->LE_CAN_CHECK_STATUS->setStyleSheet(
            "background-color:green");

    if (sharedCamel->CAMEL_DATA_NEW.rawData.find_home == 0)
        m_ui->LE_FIND_HOME_STATUS->setStyleSheet(
            "background-color:red");
    if (sharedCamel->CAMEL_DATA_NEW.rawData.find_home == 1)
        m_ui->LE_FIND_HOME_STATUS->setStyleSheet(
            "background-color:green");

    if (sharedCamel->CAMEL_DATA_NEW.rawData.control_start == 0)
        m_ui->LE_CONTROL_START_STATUS->setStyleSheet(
            "background-color:red");
    if (sharedCamel->CAMEL_DATA_NEW.rawData.control_start == 1)
        m_ui->LE_CONTROL_START_STATUS->setStyleSheet(
            "background-color:green");
}



void MotorDialog::on_BTN_AUTO_START_clicked()
{
    COMMAND_STRUCT cmd;
    cmd.USER_COMMAND = CMD_PLATFORM_AUTO_START;
    cmd.COMMAND_TARGET = CAMEL_PLATFORM;
    sharedCamel->COMMAND = cmd;
    sharedCamel->NEWCOMMAND = true;
}


void MotorDialog::on_BTN_CAN_CHECK_SEQ_clicked()
{
    COMMAND_STRUCT cmd;
    cmd.USER_COMMAND = CMD_PLATFORM_CAN_CHECK;
    cmd.COMMAND_TARGET = CAMEL_PLATFORM;
    sharedCamel->COMMAND = cmd;
    sharedCamel->NEWCOMMAND = true;
}

void MotorDialog::on_BTN_FIND_HOME_SEQ_clicked()
{
    COMMAND_STRUCT cmd;
    cmd.COMMAND_TARGET = CAMEL_PLATFORM;
    cmd.USER_COMMAND = CMD_PLATFORM_FIND_HOME;
    sharedCamel->COMMAND = cmd;
    sharedCamel->NEWCOMMAND = true;
}

void MotorDialog::on_BTN_CONTROL_START_SEQ_clicked()
{
    COMMAND_STRUCT cmd;
    cmd.USER_COMMAND = CMD_PLATFORM_CON_START;
    cmd.COMMAND_TARGET = CAMEL_PLATFORM;
    sharedCamel->COMMAND = cmd;
    sharedCamel->NEWCOMMAND = true;
}


void MotorDialog::on_BTN_BOARD_RESET_clicked()
{
    COMMAND_STRUCT cmd;
    cmd.USER_COMMAND = CMD_PLATFORM_PLATFORM_RESET;
    cmd.COMMAND_TARGET = CAMEL_PLATFORM;
    sharedCamel->COMMAND = cmd;
    sharedCamel->NEWCOMMAND = true;
}

void MotorDialog::on_BT_VOLTAGE_ON_LEG_clicked()
{
    COMMAND_STRUCT cmd;
    cmd.USER_COMMAND = CMD_PLATFORM_LEG_START;
    cmd.COMMAND_TARGET = CAMEL_PLATFORM;
    sharedCamel->COMMAND = cmd;
    sharedCamel->NEWCOMMAND = true;
}

void MotorDialog::on_BT_VOLTAGE_OFF_LEG_clicked()
{
    COMMAND_STRUCT cmd;
    cmd.USER_COMMAND = CMD_PLATFORM_LEG_STOP;
    cmd.COMMAND_TARGET = CAMEL_PLATFORM;
    sharedCamel->COMMAND = cmd;
    sharedCamel->NEWCOMMAND = true;
}

void MotorDialog::pdu_power_control(unsigned char _index, unsigned char _onoff)
{
    COMMAND_STRUCT cmd;
    // cmd.USER_COMMAND = DAEMON_PDU_POWER_CONTROL;
    cmd.COMMAND_TARGET = CAMEL_PLATFORM;
    cmd.USER_PARA_CHAR[0] = _index;
    cmd.USER_PARA_CHAR[1] = _onoff;
    sharedCamel->COMMAND = cmd;
    sharedCamel->NEWCOMMAND = true;
}