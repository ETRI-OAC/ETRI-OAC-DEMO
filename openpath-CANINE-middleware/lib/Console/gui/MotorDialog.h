#ifndef ROBOTINIT_H
#define ROBOTINIT_H

#include <QDialog>
#include <QListWidgetItem>
#include <QSettings>
#include <QTimer>

namespace Ui {
class MotorDialog;
}

class MotorDialog : public QDialog
{
    Q_OBJECT

public:
    explicit MotorDialog(QWidget *parent = 0);
    ~MotorDialog();

protected:
    virtual void hideEvent(QHideEvent *){Q_EMIT SIG_ACTION_HIDE(false);}

Q_SIGNALS:
    void SIG_ACTION_HIDE(bool);

private Q_SLOTS:
    void update();

    void on_BTN_AUTO_START_clicked();

    void on_BTN_BOARD_RESET_clicked();

    void on_BTN_CAN_CHECK_SEQ_clicked();

    void on_BTN_FIND_HOME_SEQ_clicked();

    void on_BTN_CONTROL_START_SEQ_clicked();

    void on_BT_VOLTAGE_ON_LEG_clicked();


    void on_BT_VOLTAGE_OFF_LEG_clicked();

private:

    void pdu_power_control(unsigned char _index, unsigned char _onoff);
    Ui::MotorDialog*      m_ui                = nullptr;
    QTimer*             m_updateTimer       = nullptr;
    int                 m_numOfApps         = 0;
};

#endif // ROBOTINIT_H
