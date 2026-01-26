#include "CommunicationClient.h"
#include "SharedMemory.h"
#include <cstring>
#include <algorithm>
#include <unistd.h>

// 패킷 상수
static constexpr uchar H0 = 0xF0;
static constexpr uchar H1 = 0xEF;
static constexpr uchar T0 = 0x00;
static constexpr uchar T1 = 0x0F;

CommunicationClient::CommunicationClient(QObject* parent)
    : QObject(parent)
{
    // 초기 메인 소켓(순차 연결 경로에서만 사용)
    tcpSocket = new QTcpSocket(this);
    connect(tcpSocket, &QTcpSocket::connected,    this, &CommunicationClient::onConnected);
    connect(tcpSocket, &QTcpSocket::disconnected, this, &CommunicationClient::onDisconnected);
    connect(tcpSocket, &QTcpSocket::readyRead,    this, &CommunicationClient::onReadyRead);
    connect(tcpSocket,
            QOverload<QAbstractSocket::SocketError>::of(&QTcpSocket::errorOccurred),
            this, &CommunicationClient::onSocketError);

    lastReceivedTime = QDateTime::currentDateTime();

    // 수신 타임아웃
    readTimeoutTimer = new QTimer(this);
    readTimeoutTimer->setInterval(1000);
    readTimeoutTimer->setTimerType(Qt::CoarseTimer);
    connect(readTimeoutTimer, &QTimer::timeout, this, &CommunicationClient::onReadTimeoutCheck);
    readTimeoutTimer->start();

    // 자동 연결
    autoTimer = new QTimer(this);
    autoTimer->setInterval(250);
    autoTimer->setTimerType(Qt::CoarseTimer);                 // 과도한 깨움 방지
    connect(autoTimer, &QTimer::timeout, this, &CommunicationClient::onAutoConnectTick);

    // 순차 연결 워치독(레이싱에는 미적용)
    connectWatchdog_ = new QTimer(this);
    connectWatchdog_->setInterval(200);
    connectWatchdog_->setTimerType(Qt::PreciseTimer);
    connect(connectWatchdog_, &QTimer::timeout, this, [this](){
        if (tcpSocket && tcpSocket->state() == QAbstractSocket::ConnectingState) {
            if (connectStartAt_.msecsTo(QDateTime::currentDateTime()) > connectTimeoutMs_) {
                FILE_LOG(logWARNING) << "[TCP] connect watchdog timeout -> abort";
                tcpSocket->abort();
                markDisconnected("connect timeout");
            }
        }
    });
}

void CommunicationClient::setCandidateIps(const QStringList& ips)
{
    if (!ips.isEmpty()) candidates_ = ips;
}

void CommunicationClient::startAutoConnect(int tickMs)
{
    autoTimer->setInterval(std::max(100, tickMs));
    backoffMs_ = 1000;
    nextAttemptAt_ = QDateTime::currentDateTime();
    autoTimer->start();
}

void CommunicationClient::stopAutoConnect()
{
    autoTimer->stop();
}

void CommunicationClient::Connect(QString ip)
{
    if (!tcpSocket || tcpSocket->state() != QAbstractSocket::UnconnectedState) return;

    currentIp_ = ip;
    FILE_LOG(logINFO) << "[TCP] Trying connect to " << ip.toStdString() << ":" << tcpPort_;
    connectStartAt_ = QDateTime::currentDateTime();
    tcpSocket->connectToHost(ip, tcpPort_);
    if (!connectWatchdog_->isActive()) connectWatchdog_->start();
}

void CommunicationClient::Disconnect()
{
    buffer.clear();
    stopRacing_("manual disconnect");
    if (tcpSocket) tcpSocket->disconnectFromHost();
    // onDisconnected()에서 정리
}

bool CommunicationClient::sendCommand(const COMMAND_STRUCT& cmd)
{
    if (!tcpSocket || tcpSocket->state() != QAbstractSocket::ConnectedState) {
        FILE_LOG(logWARNING) << "[TCP] sendCommand dropped (not connected)";
        return false;
    }
    const char* raw = reinterpret_cast<const char*>(&cmd);
    const int   len = static_cast<int>(sizeof(COMMAND_STRUCT));
    QByteArray bytes = QByteArray::fromRawData(raw, len);
    const qint64 n = tcpSocket->write(bytes);
    if (n < 0) {
        FILE_LOG(logERROR) << "[TCP] write() failed";
        return false;
    }
    emit tcpBytesWritten(n);
    FILE_LOG(logINFO) << "[TCP] sendCommand queued " << n << " bytes";
    return true;
}

bool CommunicationClient::sendRaw(const QByteArray& bytes)
{
    if (!tcpSocket || tcpSocket->state() != QAbstractSocket::ConnectedState) {
        FILE_LOG(logWARNING) << "[TCP] sendRaw dropped (not connected)";
        return false;
    }
    const qint64 n = tcpSocket->write(bytes);
    if (n < 0) {
        FILE_LOG(logERROR) << "[TCP] write() failed";
        return false;
    }
    emit tcpBytesWritten(n);
    FILE_LOG(logINFO) << "[TCP] sendRaw queued " << n << " bytes";
    return true;
}

// ====== 단일 소켓(순차 연결) 경로 ======
void CommunicationClient::onConnected()
{
    FILE_LOG(logSUCCESS) << "[TCP] Connected to " << currentIp_.toStdString();
    bIsConnect_ = true;
    if (sharedCamel) sharedCamel->bIsConnect = true;
    resetBackoffOnSuccess();
    connectWatchdog_->stop();
    emit tcpConnected(currentIp_);
}

void CommunicationClient::onDisconnected()
{
    // sender 검사: 승자 소켓만 처리
    if (sender() && sender() != tcpSocket) return;
    markDisconnected("QTcpSocket disconnected()");
}

void CommunicationClient::onSocketError(QAbstractSocket::SocketError)
{
    if (sender() && sender() != tcpSocket) return;
    FILE_LOG(logWARNING) << "[TCP] socket error "
                         << (tcpSocket ? tcpSocket->errorString().toStdString() : std::string("no socket"));
    markDisconnected("socket error");
}

// ====== 공통 ======
void CommunicationClient::onReadTimeoutCheck()
{
    if (bIsConnect_) {
        if (lastReceivedTime.msecsTo(QDateTime::currentDateTime()) > readTimeoutMs_) {
            FILE_LOG(logWARNING) << "[TCP] Read timeout (> " << readTimeoutMs_ << " ms). Aborting socket.";
            if (tcpSocket) tcpSocket->abort();
            // onDisconnected/onSocketError에서 후속 처리
        }
    }
}

void CommunicationClient::onAutoConnectTick()
{
    if (bIsConnect_) return;
    if (QDateTime::currentDateTime() < nextAttemptAt_) return;

    // 순차 연결 시도 중이면 워치독이 처리
    if (tcpSocket && tcpSocket->state() == QAbstractSocket::ConnectingState) return;

    // 🔒 레이싱 진행 중이면 재시작 금지
    if (isRaceActive_()) return;

    // 레이싱 시작
    startRacingConnect_();
}

void CommunicationClient::tryNextIp()
{
    if (candidates_.isEmpty()) return;
    const QString ip = candidates_[ipIndex_];
    ipIndex_ = (ipIndex_ + 1) % candidates_.size();
    Connect(ip);
}

void CommunicationClient::markDisconnected(const char* reason)
{
    if (bIsConnect_)
        FILE_LOG(logWARNING) << "[TCP] Disconnected from " << currentIp_.toStdString()
                             << " (" << (reason ? reason : "") << ")";
    bIsConnect_ = false;
    if (sharedCamel) sharedCamel->bIsConnect = false;
    emit tcpDisconnected(currentIp_, reason ? QString::fromUtf8(reason) : QString());
    currentIp_.clear();

    connectWatchdog_->stop();

    // 레이싱 중 정지
    stopRacing_("disconnected");

    // 백오프 스케줄
    nextAttemptAt_ = QDateTime::currentDateTime().addMSecs(backoffMs_);
}

void CommunicationClient::resetBackoffOnSuccess()
{
    backoffMs_ = 1000;
    nextAttemptAt_ = QDateTime::currentDateTime();
}

void CommunicationClient::onReadyRead()
{
    // 승자 소켓만 처리
    if (auto* s = qobject_cast<QTcpSocket*>(sender())) {
        if (tcpSocket && s != tcpSocket) { s->readAll(); return; }
    } else {
        if (!tcpSocket) return;
    }

    lastReceivedTime = QDateTime::currentDateTime();
    buffer.append(tcpSocket->readAll());

    // 버퍼 상한
    constexpr int kMaxBuf = 1 << 20; // 1MB
    if (buffer.size() > kMaxBuf) {
        FILE_LOG(logWARNING) << "[TCP] buffer overflow (" << buffer.size() << "), clearing.";
        buffer.clear();
        return;
    }

    // 고정 패킷: [F0 EF][payload(sizeof(LAN_CAMEL2GUI))][00 0F]
    constexpr int headerSize  = 2;
    constexpr int tailSize    = 2;
    const int payloadSize = static_cast<int>(sizeof(LAN_CAMEL2GUI));
    const int packetSize  = headerSize + payloadSize + tailSize;

    int processed = 0, kMaxProcessPerRead = 64; // 1회 콜백 최대 64패킷
    while (buffer.size() >= packetSize && processed < kMaxProcessPerRead)
    {
        int idx = buffer.indexOf(QByteArray::fromRawData("\xF0\xEF", 2));
        if (idx < 0) { buffer.clear(); break; }
        if (idx > 0) buffer.remove(0, idx);
        if (buffer.size() < packetSize) break;

        const uchar* raw = reinterpret_cast<const uchar*>(buffer.constData());
        if (raw[packetSize - 2] == T0 && raw[packetSize - 1] == T1)
        {
            LAN_CAMEL2GUI newCamelData;
            std::memcpy(&newCamelData, buffer.constData() + headerSize, payloadSize);
            buffer.remove(0, packetSize);

            if (sharedCamel) sharedCamel->CAMEL_DATA_NEW = newCamelData;
            ++processed;
        }
        else {
            buffer.remove(0, headerSize); // 헤더만 제거해 재동기화
            ++processed;
        }
    }
}

// ====== 레이싱 연결 ======
void CommunicationClient::startRacingConnect_()
{
    if (candidates_.isEmpty()) return;
    if (isRaceActive_()) return; // 이중 시작 방지

    // 다음 자동시도 시각을 레이스 끝 이후로 밀어 재진입 억제
    nextAttemptAt_ = QDateTime::currentDateTime().addMSecs(raceTimeoutMs_ + 100);

    // 기존 메인 소켓 정리(시그널/객체)
    if (tcpSocket) {
        detachAllSignals_(tcpSocket);
        if (tcpSocket->state() != QAbstractSocket::UnconnectedState) tcpSocket->abort();
        tcpSocket->deleteLater();
        tcpSocket = nullptr;
    }

    // 레이싱 시작
    stopRacing_("restart"); // 혹시 남아있다면 정리

    const int k = std::min(2, candidates_.size()); // 동시 시도 개수
    race_.reserve(k);

    FILE_LOG(logINFO) << "[TCP] Racing connect to " << k << " candidates";
    for (int i = 0; i < k; ++i) {
        auto* s = new QTcpSocket(this);
        RaceSock rs{ s, candidates_[(ipIndex_ + i) % candidates_.size()] };

        // 레이싱 동안엔 connected/error만 받는다 (readyRead/disconnected 미연결!)
        connect(s, &QTcpSocket::connected, this, &CommunicationClient::onRaceConnected_);
        connect(s, QOverload<QAbstractSocket::SocketError>::of(&QTcpSocket::errorOccurred),
                this, &CommunicationClient::onRaceError_);

        FILE_LOG(logINFO) << "[TCP] -> try " << rs.ip.toStdString() << ":" << tcpPort_;
        s->connectToHost(rs.ip, tcpPort_);
        race_.push_back(rs);
    }
    // 다음 라운드 시작 인덱스 회전
    ipIndex_ = (ipIndex_ + k) % candidates_.size();

    // 레이스 타임아웃
    if (!raceTimer_) {
        raceTimer_ = new QTimer(this);
        raceTimer_->setSingleShot(true);
        raceTimer_->setTimerType(Qt::PreciseTimer);
        connect(raceTimer_, &QTimer::timeout, this, [this](){
            FILE_LOG(logWARNING) << "[TCP] race timeout";
            stopRacing_("timeout");
            // 레이스 실패 → 백오프 증가
            nextAttemptAt_ = QDateTime::currentDateTime().addMSecs(backoffMs_);
        });
    }
    raceTimer_->start(raceTimeoutMs_);
}

void CommunicationClient::onRaceConnected_()
{
    if (promoting_) return;      // 재진입 방지
    promoting_ = true;

    auto* winner = qobject_cast<QTcpSocket*>(sender());
    if (!winner) { promoting_ = false; return; }

    QString winIp;
    for (auto& r : race_) if (r.sock == winner) { winIp = r.ip; break; }
    FILE_LOG(logSUCCESS) << "[TCP] Racing WIN -> " << winIp.toStdString();

    // 패자 정리(지연 삭제)
    for (auto& r : race_) {
        if (r.sock && r.sock != winner) {
            QTcpSocket* s = r.sock;
            s->disconnect(this);
            QTimer::singleShot(0, [s](){ s->abort(); s->deleteLater(); });
        }
    }
    race_.clear();
    if (raceTimer_) { raceTimer_->stop(); raceTimer_->deleteLater(); raceTimer_ = nullptr; }

    // 승자를 메인 소켓으로 승격
    tcpSocket = winner;
    currentIp_ = winIp;

    // 승자에만 본 시그널 연결
    attachMainSocketSignals_();

    // 상태 갱신
    connectWatchdog_->stop(); // 레이싱에는 미사용
    resetBackoffOnSuccess();
    bIsConnect_ = true;
    if (sharedCamel) sharedCamel->bIsConnect = true;
    lastReceivedTime = QDateTime::currentDateTime();

    emit tcpConnected(currentIp_);
    promoting_ = false;
}

void CommunicationClient::onRaceError_(QAbstractSocket::SocketError)
{
    QTcpSocket* loser = qobject_cast<QTcpSocket*>(sender());
    if (!loser) return;
    // 승자 소켓이면 여기서 취급하지 않음
    if (loser == tcpSocket) return;

    loser->disconnect(this);
    loser->deleteLater();

    // race_ 목록에서도 제거
    for (int i = 0; i < race_.size(); ++i) {
        if (race_[i].sock == loser) { race_.remove(i); break; }
    }
}

void CommunicationClient::stopRacing_(const char* why)
{
    if (raceTimer_) { raceTimer_->stop(); raceTimer_->deleteLater(); raceTimer_ = nullptr; }
    if (!race_.isEmpty())
        FILE_LOG(logINFO) << "[TCP] stop racing (" << (why ? why : "") << ")";
    for (auto& r : race_) {
        if (r.sock) {
            QTcpSocket* s = r.sock;
            s->disconnect(this);
            QTimer::singleShot(0, [s](){ s->abort(); s->deleteLater(); });
        }
    }
    race_.clear();
}

void CommunicationClient::detachAllSignals_(QTcpSocket* s)
{
    if (!s) return;
    s->disconnect(this);
}

void CommunicationClient::attachMainSocketSignals_() //
{
    if (!tcpSocket) return;
    // 중복 연결 방지: 먼저 끊고 다시 연결
    tcpSocket->disconnect(this);

    connect(tcpSocket, &QTcpSocket::readyRead,    this, &CommunicationClient::onReadyRead);
    connect(tcpSocket, &QTcpSocket::disconnected, this, &CommunicationClient::onDisconnected);
    connect(tcpSocket,
            QOverload<QAbstractSocket::SocketError>::of(&QTcpSocket::errorOccurred),
            this, &CommunicationClient::onSocketError);
}

bool CommunicationClient::isRaceActive_() const
{
    return !race_.isEmpty() || (raceTimer_ && raceTimer_->isActive());
}
