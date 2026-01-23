#ifndef CAMEL_QUAD_LOG_HPP
#define CAMEL_QUAD_LOG_HPP

#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <ctime>
#include <iomanip>
#include <mutex>
#include <regex>

#include <filesystem>

// 로그 레벨 정의
enum TLogLevel
{
    logERROR,
    logWARNING,
    logSUCCESS,
    logINFO,
    logDEBUG
};
extern std::string AL_NAME;

// ANSI 색상 코드
const std::string RED     = "\033[1;31m";
const std::string GREEN   = "\033[1;32m";
const std::string YELLOW  = "\033[1;33m";
const std::string BLUE    = "\033[1;34m";
const std::string MAGENTA = "\033[1;35m";
const std::string GRAY    = "\033[1;90m";
const std::string RESET   = "\033[0m";

// 로그 레벨을 문자열로 변환
inline std::string ToString(TLogLevel level)
{
    switch (level)
    {
    case logERROR:
        return "ERROR";
    case logWARNING:
        return "WARNING";
    case logSUCCESS:
        return "SUCCESS";
    case logINFO:
        return "INFO";
    case logDEBUG:
        return "DEBUG";
    default:
        return "UNKNOWN";
    }
}

// 현재 시간을 로그용 문자열로 반환
inline std::string NowTime()
{
    using namespace std::chrono;

    auto now = system_clock::now();
    auto now_time_t = system_clock::to_time_t(now);
    auto now_ms = duration_cast<milliseconds>(now.time_since_epoch()) % 1000;

    std::ostringstream oss;
    std::tm now_tm = *std::localtime(&now_time_t);
    oss << std::put_time(&now_tm, "%H:%M:%S") << '.' << std::setfill('0') << std::setw(3) << now_ms.count();

    return oss.str();
}

inline std::string get_current_time_for_filename()
{
    auto now = std::time(nullptr);
    std::ostringstream ss;
    ss << std::put_time(std::localtime(&now), "%Y-%m-%d_%H-%M-%S");
    return ss.str();
}

// Log 클래스
class Log
{
public:
    Log(TLogLevel level)
        : level(level)
    {
        std::lock_guard<std::mutex> lock(mtx);

        // 로그 레벨에 따른 색상 적용 (터미널용)
        switch (level)
        {
        case logERROR:   os << RED; break;
        case logWARNING: os << YELLOW; break;
        case logSUCCESS: os << GREEN; break;
        case logINFO:    os << BLUE; break;
        case logDEBUG:   os << GRAY; break;
        default: break;
        }

        // 로그 포맷 설정
        os << "[" << AL_NAME << "] [" << NowTime() << "] [" << ToString(level) << "] ";
    }

    ~Log()
    {
        std::lock_guard<std::mutex> lock(mtx);

        // 터미널에 출력
        std::cout << os.str() << RESET << std::endl;

        // 파일에 출력 (색상 코드 제거)
        if (log_file.is_open())
        {
            log_file << RemoveColorCodes(os.str()) << std::endl;
        }
    }

    template <typename T>
    Log& operator<<(const T& message)
    {
        os << message;
        return *this;
    }

    static void initLogFile(const std::string& directory, const std::string& filename)
    {
        std::lock_guard<std::mutex> lock(mtx);

        // 디렉토리 생성 (필요한 경우)
        if (!std::filesystem::exists(directory))
        {
            std::filesystem::create_directories(directory);
        }

        // 경로와 파일명을 결합하여 전체 경로 생성
        std::string filepath = directory + "/" + filename;

        log_file.open(filepath, std::ios::app);
        if (!log_file.is_open())
        {
            std::cerr << "Failed to open log file: " << filepath << std::endl;
        }
    }

    static void closeLogFile()
    {
        std::lock_guard<std::mutex> lock(mtx);
        if (log_file.is_open())
        {
            log_file.close();
        }
    }

private:
    std::ostringstream os;
    TLogLevel level;
    static std::ofstream log_file;
    static std::mutex mtx;

    // ANSI 색상 코드를 제거하는 함수
    std::string RemoveColorCodes(const std::string& str)
    {
        // 정규 표현식을 사용해 ANSI 색상 코드 제거
        std::regex color_code_regex("\033\\[[0-9;]*m");
        return std::regex_replace(str, color_code_regex, "");
    }
};

// 정적 멤버 초기화
inline std::ofstream Log::log_file;
inline std::mutex Log::mtx;

// 매크로로 로그를 출력하고 파일에 기록
#define FILE_LOG(level) Log(level)

#endif // CAMEL_QUAD_LOG_HPP
