#pragma once

#include <QObject>
#include <QTcpSocket>
#include <QTimer>
#include <QByteArray>
#include <QDateTime>
#include <QStringList>
#include <QVector>
#include <CAMEL_SDK/CAMEL_api.hpp>

class CommunicationClient : public QObject
{
    Q_OBJECT
public:
    explicit CommunicationClient(QObject* parent = nullptr);
    ~CommunicationClient() override = default;

    void setCandidateIps(const QStringList& ips);
    void setTcpPort(quint16 port) { tcpPort_ = port; }

    void startAutoConnect(int tickMs = 250);
    void stopAutoConnect();

    // 순차 연결(특정 IP 강제 시도 시만 사용; 기본은 startAutoConnect의 레이싱 경로 사용)
    void Connect(QString ip);
    void Disconnect();

    bool sendCommand(const COMMAND_STRUCT& cmd);
    bool sendRaw(const QByteArray& bytes);

signals:
    void tcpConnected(const QString& ip);
    void tcpDisconnected(const QString& ip, const QString& reason);
    void tcpBytesWritten(qint64 n);

private slots:
    // 단일 소켓(순차 연결) 경로
    void onConnected();
    void onDisconnected();
    void onSocketError(QAbstractSocket::SocketError err);

    void onReadyRead();
    void onReadTimeoutCheck();
    void onAutoConnectTick();

    // 레이싱 연결
    void onRaceConnected_();
    void onRaceError_(QAbstractSocket::SocketError);

private:
    void tryNextIp();                       // 순차 연결 모드용
    void markDisconnected(const char* reason);
    void resetBackoffOnSuccess();

    // 레이싱 연결
    struct RaceSock {
        QTcpSocket* sock{nullptr};
        QString     ip;
    };
    void startRacingConnect_();
    void stopRacing_(const char* why);

    void detachAllSignals_(QTcpSocket* s);
    void attachMainSocketSignals_();

    // 레이싱 진행 중 여부 가드
    bool isRaceActive_() const;

private:
    // 메인(승자) 소켓
    QTcpSocket* tcpSocket{nullptr};
    QString     currentIp_;
    quint16     tcpPort_{18001};   // port
    bool        bIsConnect_{false};

    // 후보/자동 재연결
    QStringList candidates_;
    int         ipIndex_{0};
    QTimer*     autoTimer{nullptr};

    // 연결 워치독(순차 연결 시만 사용)
    QTimer*     connectWatchdog_{nullptr};
    QDateTime   connectStartAt_;
    const int   connectTimeoutMs_{1500};

    // 수신 타임아웃
    QTimer*     readTimeoutTimer{nullptr};
    int         readTimeoutMs_{1500};
    QDateTime   lastReceivedTime;

    // 백오프
    int         backoffMs_{1000};
    const int   backoffMaxMs_{8000};
    QDateTime   nextAttemptAt_;

    // 수신 버퍼
    QByteArray  buffer;

    // 레이싱 상태
    QVector<RaceSock> race_;
    QTimer*     raceTimer_{nullptr};
    int         raceTimeoutMs_{1500};
    bool        promoting_{false}; // 승자 승격 재진입 방지
};
