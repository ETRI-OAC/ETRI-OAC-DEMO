#ifndef OPERATION_H
#define OPERATION_H

#include <Eigen/Dense>
#include <Eigen/Core>
#include <iostream>

//inline float sign(float a){return (a<0 ? -1.0f : 1.0f);}
inline float signf(float a){return (a<0 ? -1.0 : 1.0);}

#define PI 3.14159265359

/*!
 * frequently-used Vector, Matrix
 */
using Vec2f  = Eigen::Matrix<float, 2, 1>;      using Vec2d  = Eigen::Matrix<double, 2, 1>;
using Vec3f  = Eigen::Matrix<float, 3, 1>;      using Vec3d  = Eigen::Matrix<double, 3, 1>;
using Vec4f  = Eigen::Matrix<float, 4, 1>;      using Vec4d  = Eigen::Matrix<double, 4, 1>;
using Vec5f  = Eigen::Matrix<float, 5, 1>;      using Vec5d  = Eigen::Matrix<double, 5, 1>;
using Vec6f  = Eigen::Matrix<float, 6, 1>;      using Vec6d  = Eigen::Matrix<double, 6, 1>;
using Vec12f = Eigen::Matrix<float, 12, 1>;     using Vec12d = Eigen::Matrix<double, 12, 1>;
using Vec18f = Eigen::Matrix<float, 18, 1>;     using Vec18d = Eigen::Matrix<double, 18, 1>;

using Mat2f = Eigen::Matrix<float, 2, 2>;       using Mat2d = Eigen::Matrix<double, 2, 2>;
using Mat3f = Eigen::Matrix<float, 3, 3>;       using Mat3d = Eigen::Matrix<double, 3, 3>;
using Mat4f = Eigen::Matrix<float, 4, 4>;       using Mat4d = Eigen::Matrix<double, 4, 4>;
using Mat6f = Eigen::Matrix<float, 6, 6>;       using Mat6d = Eigen::Matrix<double, 6, 6>;

namespace Operation{
//public:
//    static Eigen::Matrix3f quat2ROT(const Eigen::Vector4f quat){

//        float w, x, y, z;
//        w=quat(0), x=quat(1), y=quat(2), z=quat(3);

//        float xx, yy, zz, wx, wy, wz, xy, yz, zx;
//        xx = 2*x*x, yy = 2*y*y, zz = 2*z*z;
//        wx = 2*w*x, wy = 2*w*y, wz = 2*w*z;
//        xy = 2*x*y, yz = 2*y*z, zx = 2*z*x;

//        Eigen::Matrix3f R;
//        R(0,0) = 1.0f-yy-zz; R(0,1) =      xy-wz; R(0,2) =      zx+wy;
//        R(1,0) =      xy+wz; R(1,1) = 1.0f-xx-zz; R(1,2) =      yz-wx;
//        R(2,0) =      zx-wy; R(2,1) =      yz+wx; R(2,2) = 1.0f-xx-yy;

//        return R;
//    }

//    static Eigen::Vector3f quat2RPY(const Eigen::Vector4f quat){
//        //quat(0) = w, quat(1) = x, quat(2) = y, quat(3) = z
//        float sinr_cosp = 2 * (quat(0) * quat(1) + quat(2) * quat(3));
//        float cosr_cosp = 1 - 2 * (quat(1) * quat(1) + quat(2) * quat(2));
//        float roll = std::atan2(sinr_cosp, cosr_cosp);

//        float sinp = 2 * (quat(0) * quat(2) - quat(3) * quat(1));
//        float pitch;
//        if(std::abs(sinp) >= 1)
//          pitch = std::copysign(PI / 2, sinp);
//        else
//          pitch = std::asin(sinp);

//        float siny_cosp = 2 * (quat(0) * quat(3) + quat(1) * quat(2));
//        float cosy_cosp = 1 - 2 * (quat(2) * quat(2) + quat(3) * quat(3));
//        float yaw = std::atan2(siny_cosp, cosy_cosp);

//        Eigen::Vector3f rpy(roll, pitch, yaw);
//        return rpy;
//    }

//    static Eigen::Vector4f rot2QUAT(Eigen::Matrix3f m){
//        Eigen::Vector4f QUAT;
//        QUAT(0) = 0.5f*sqrt(1.0f+m(0,0)+m(1,1)+m(2,2));
//        QUAT(1) = sign(m(2,1)-m(1,2))*0.5f*sqrt(1+m(0,0)-m(1,1)-m(2,2));
//        QUAT(2) = sign(m(0,2)-m(2,0))*0.5f*sqrt(1-m(0,0)+m(1,1)-m(2,2));
//        QUAT(3) = sign(m(1,0)-m(0,1))*0.5f*sqrt(1-m(0,0)-m(1,1)+m(2,2));
//        if(QUAT(0)*QUAT(0) + QUAT(1)*QUAT(1)
//                + QUAT(2)*QUAT(2) + QUAT(3)*QUAT(3) <0.001)
//        {QUAT(0) = 1.0f;}

//        return QUAT;
//    }

//    static Eigen::Vector4f rpy2QUAT(Eigen::Vector3f rpy){
//        Eigen::Vector4f QUAT;

//        float cr = cos(rpy.x()/2), cp = cos(rpy.y()/2), cy = cos(rpy.z()/2);
//        float sr = sin(rpy.x()/2), sp = sin(rpy.y()/2), sy = sin(rpy.z()/2);
//        QUAT(0) = cr*cp*cy + sr*sp*sy;
//        QUAT(1) = sr*cp*cy - cr*sp*sy;
//        QUAT(2) = cr*sp*cy + sr*cp*sy;
//        QUAT(3) = cr*cp*sy - sr*sp*cy;

//        return QUAT;
//    }

//    static Eigen::Vector4f quatProduct(const Eigen::Vector4f &a,
//                                const Eigen::Vector4f &b) {
//        Eigen::Vector4f ab;
//        ab(0) = a(0)*b(0) - a(1)*b(1) - a(2)*b(2) - a(3)*b(3);
//        ab(1) = a(0)*b(1) + a(1)*b(0) + a(2)*b(3) - a(3)*b(2);
//        ab(2) = a(0)*b(2) - a(1)*b(3) + a(2)*b(0) + a(3)*b(1);
//        ab(3) = a(0)*b(3) + a(1)*b(2) - a(2)*b(1) + a(3)*b(0);

//        return ab;
//    }

//    static Eigen::Matrix3f diagonalize3f(const float a, const float b, const float c){
//        Eigen::Matrix3f A;
//        A << a, 0, 0,
//             0, b, 0,
//             0, 0, c;
//        return A;
//    }

//    static Eigen::Matrix3f vec2HAT(Eigen::Vector3f vec)
//    {
//        Eigen::Matrix3f hatMat = Eigen::Matrix3f::Zero();
//        hatMat(0,1) = -vec[2];
//        hatMat(0,2) = vec[1];
//        hatMat(1,0) = vec[2];
//        hatMat(1,2) = -vec[0];
//        hatMat(2,0) = -vec[1];
//        hatMat(2,1) = vec[0];

//        return hatMat;
//    }


    static Eigen::Vector4f rot2QUAT(Eigen::Matrix3f m){
        Eigen::Vector4f QUAT;
//        QUAT(0) = 0.5f*sqrt(1.0f+m(0,0)+m(1,1)+m(2,2));
//        QUAT(1) = signf(m(2,1)-m(1,2))*0.5f*sqrt(1+m(0,0)-m(1,1)-m(2,2));
//        QUAT(2) = signf(m(0,2)-m(2,0))*0.5f*sqrt(1-m(0,0)+m(1,1)-m(2,2));
//        QUAT(3) = signf(m(1,0)-m(0,1))*0.5f*sqrt(1-m(0,0)-m(1,1)+m(2,2));
//        if(QUAT(0)*QUAT(0) + QUAT(1)*QUAT(1)
//                + QUAT(2)*QUAT(2) + QUAT(3)*QUAT(3) <0.001)
//        {QUAT(0) = 1.0f;}

        QUAT(0) = 0.5f*sqrt(1.0f+m(0,0)+m(1,1)+m(2,2));
        QUAT(1) = 0.25f/QUAT(0)*(m(2,1) - m(1,2));
        QUAT(2) = 0.25f/QUAT(0)*(m(0,2) - m(2,0));
        QUAT(3) = 0.25f/QUAT(0)*(m(1,0) - m(0,1));

        return QUAT;
    }

    static Eigen::Matrix3f quat2ROT(const Eigen::Vector4f quat){

        float w, x, y, z;
        w=quat(0), x=quat(1), y=quat(2), z=quat(3);

        float xx, yy, zz, wx, wy, wz, xy, yz, zx;
        xx = 2*x*x, yy = 2*y*y, zz = 2*z*z;
        wx = 2*w*x, wy = 2*w*y, wz = 2*w*z;
        xy = 2*x*y, yz = 2*y*z, zx = 2*z*x;

        Eigen::Matrix3f R;
        R(0,0) = 1.0 -yy-zz; R(0,1) =      xy-wz; R(0,2) =      zx+wy;
        R(1,0) =      xy+wz; R(1,1) = 1.0 -xx-zz; R(1,2) =      yz-wx;
        R(2,0) =      zx-wy; R(2,1) =      yz+wx; R(2,2) = 1.0 -xx-yy;

        return R;
    }

    static Eigen::Vector3f quat2RPY(const Eigen::Vector4f quat){ // w, x, y, z
        //quat(0) = w, quat(1) = x, quat(2) = y, quat(3) = z
        // yaw-pitch-roll Euler Angle transform
        float sinr_cosp = 2 * (quat(0) * quat(1) + quat(2) * quat(3));
        float cosr_cosp = 1 - 2 * (quat(1) * quat(1) + quat(2) * quat(2));
        float roll = std::atan2(sinr_cosp, cosr_cosp);

        float sinp = 2 * (quat(0) * quat(2) - quat(3) * quat(1));
        float pitch;
        if(std::abs(sinp) >= 1)
          pitch = std::copysign(PI / 2, sinp);
        else
          pitch = std::asin(sinp);

        float siny_cosp = 2 * (quat(0) * quat(3) + quat(1) * quat(2));
        float cosy_cosp = 1 - 2 * (quat(2) * quat(2) + quat(3) * quat(3));
        float yaw = std::atan2(siny_cosp, cosy_cosp);

        Eigen::Vector3f rpy(roll, pitch, yaw);
        return rpy;

// mit cheetah version
//        //edge case!
//        fpt as = t_min(-2.*(q.x()*q.z()-q.w()*q.y()),.99999);
//        rpy(0) = atan2(2.f*(q.x()*q.y()+q.w()*q.z()),sq(q.w()) + sq(q.x()) - sq(q.y()) - sq(q.z()));
//        rpy(1) = asin(as);
//        rpy(2) = atan2(2.f*(q.y()*q.z()+q.w()*q.x()),sq(q.w()) - sq(q.x()) - sq(q.y()) + sq(q.z()));
    }

    static Eigen::Vector3f quat2RPY2(const Eigen::Vector4f quat){ // w, x, y, z
        //quat(0) = w, quat(1) = x, quat(2) = y, quat(3) = z
        float roll = atan2(2 * (quat(2)*quat(3) + quat(0)*quat(1)), 1 - 2 * (quat(1)*quat(1) + quat(2)*quat(2)));
        float pitch = -1 * asin(2 * (quat(1)*quat(3) - quat(0)*quat(2)));
        float yaw = atan2(2 * (quat(1)*quat(2) + quat(0)*quat(3)), 1 - 2 * (quat(2)*quat(2) + quat(3)*quat(3)));

        Eigen::Vector3f rpy(roll, pitch, yaw);
        return rpy;
    }

    static Eigen::Vector4f rpy2QUAT(Eigen::Vector3f rpy){
        Eigen::Vector4f QUAT;

        float cr = cos(rpy.x()/2), cp = cos(rpy.y()/2), cy = cos(rpy.z()/2);
        float sr = sin(rpy.x()/2), sp = sin(rpy.y()/2), sy = sin(rpy.z()/2);
        QUAT(0) = cr*cp*cy + sr*sp*sy;
        QUAT(1) = sr*cp*cy - cr*sp*sy;
        QUAT(2) = cr*sp*cy + sr*cp*sy;
        QUAT(3) = cr*cp*sy - sr*sp*cy;

        return QUAT;
    }

    static Eigen::Matrix3f rpy2ROT(Eigen::Vector3f rpy){
        return quat2ROT(rpy2QUAT(rpy));
    }

    static Eigen::Vector4f quatProduct(const Eigen::Vector4f &a,
                                         const Eigen::Vector4f &b) {
        Eigen::Vector4f ab;
        ab(0) = a(0)*b(0) - a(1)*b(1) - a(2)*b(2) - a(3)*b(3);
        ab(1) = a(0)*b(1) + a(1)*b(0) + a(2)*b(3) - a(3)*b(2);
        ab(2) = a(0)*b(2) - a(1)*b(3) + a(2)*b(0) + a(3)*b(1);
        ab(3) = a(0)*b(3) + a(1)*b(2) - a(2)*b(1) + a(3)*b(0);

        return ab;
    }

    static Eigen::Matrix3f diagonalize3f(const float a, const float b, const float c){
        Eigen::Matrix3f A;
        A << a, 0, 0,
             0, b, 0,
             0, 0, c;
        return A;
    }


    static Eigen::Matrix3f vec2HAT(Eigen::Vector3f vec)
    {
        Eigen::Matrix3f hatMat = Eigen::Matrix3f::Zero();
        hatMat(0,1) = -vec[2];
        hatMat(0,2) = vec[1];
        hatMat(1,0) = vec[2];
        hatMat(1,2) = -vec[0];
        hatMat(2,0) = -vec[1];
        hatMat(2,1) = vec[0];

        return hatMat;
    }

    static Eigen::Vector3f rot2RPY(Eigen::Matrix3f mat){
        Eigen::Vector3f rpy;

        if( mat(0,0) == 0 && mat(1,0) == 0){
            rpy(0) = atan2(mat(0,1), mat(1,1));
            rpy(1) = PI/2;
            rpy(2) = 0.0;
            std::cout<<"rot2RPY Warning!! pitch is PI/2"<<std::endl;
        }
        else{
            rpy(0) = atan2(mat(2,1), mat(2,2));
            rpy(1) = atan2(-mat(2,0), sqrt(mat(0,0)*mat(0,0) + mat(1,0)*mat(1,0)));
            rpy(2) = atan2(mat(1,0), mat(0,0));
        }

        return rpy;

    }

    static Eigen::Vector3f rot2RPY_2(Eigen::Matrix3f mat){
        Eigen::Vector3f rpy;

        if( mat(0,0) > -0.01 && mat(0,0) < 0.01 && mat(1,0) > -0.01 && mat(1,0) < 0.01){
            if(mat(2,0) > 0){
                rpy(0) = atan2(mat(0,1), mat(1,1));
                rpy(1) = -PI/2;
                rpy(2) = 0.0;
            }
            if(mat(2,0) < 0){
                rpy(0) = atan2(mat(0,1), mat(1,1));
                rpy(1) = PI/2;
                rpy(2) = 0.0;
            }
        }
        else{
            if(mat(0,0) >= 0){
                rpy(0) = atan2(mat(2,1), mat(2,2));
                rpy(1) = atan2(-mat(2,0), sqrt(mat(0,0)*mat(0,0) + mat(1,0)*mat(1,0)));
                rpy(2) = atan2(mat(1,0), mat(0,0));
            }
            else{
                rpy(0) = atan2(mat(2,1), -mat(2,2));
                rpy(1) = atan2(-mat(2,0), -sqrt(mat(0,0)*mat(0,0) + mat(1,0)*mat(1,0)));
                rpy(2) = atan2(mat(1,0), -mat(0,0));

                if(rpy(0) > PI)
                    rpy(0) = atan2(mat(2,1), -mat(2,2)) - 2*PI;
                else if(rpy(0) < -PI)
                    rpy(0) = atan2(mat(2,1), -mat(2,2)) + 2*PI;

                if(rpy(2) > PI)
                    rpy(2) = atan2(mat(1,0), -mat(0,0)) - 2*PI;
                else if(rpy(2) < -PI)
                    rpy(2) = atan2(mat(1,0), -mat(0,0)) + 2*PI;
            }
        }

        return rpy;
    }

    static Eigen::Vector4f rot2AXAN(Eigen::Matrix3f mat){
        Eigen::Vector4f axan; // (x,y,z,angle)

        axan[0] = (mat(2,1)-mat(1,2)) / sqrt( (mat(2,1)-mat(1,2))*(mat(2,1)-mat(1,2)) + (mat(0,2)-mat(2,0))*(mat(0,2)-mat(2,0)) + (mat(1,0) - mat(0,1))*(mat(1,0) - mat(0,1)) );
        axan[1] = (mat(0,2)-mat(2,0)) / sqrt( (mat(2,1)-mat(1,2))*(mat(2,1)-mat(1,2)) + (mat(0,2)-mat(2,0))*(mat(0,2)-mat(2,0)) + (mat(1,0) - mat(0,1))*(mat(1,0) - mat(0,1)) );
        axan[2] = (mat(1,0)-mat(0,1)) / sqrt( (mat(2,1)-mat(1,2))*(mat(2,1)-mat(1,2)) + (mat(0,2)-mat(2,0))*(mat(0,2)-mat(2,0)) + (mat(1,0) - mat(0,1))*(mat(1,0) - mat(0,1)) );
        axan[3] = acos((mat(0,0) + mat(1,1) + mat(2,2) - 1)/2);

        if(std::isnan(axan[3])){
            axan[3] = 0;
        }

        return axan;

    }

    static Eigen::Matrix3f axan2ROT(Eigen::Vector4f axan){
        Eigen::Matrix3f K, I, rot;
        Eigen::Vector3f n;
        I = Eigen::Matrix3f::Identity();
        float theta = axan(3);

        n.x() = axan(0) / sqrt(axan(0)*axan(0) + axan(1)*axan(1) + axan(2)*axan(2));
        n.y() = axan(1) / sqrt(axan(0)*axan(0) + axan(1)*axan(1) + axan(2)*axan(2));
        n.z() = axan(2) / sqrt(axan(0)*axan(0) + axan(1)*axan(1) + axan(2)*axan(2));

        K <<      0, -n.z(),   n.y(),
            n.z(),      0,  -n.x(),
            -n.y(),  n.x(),       0;

        rot = I + sin(theta)*K + (1-cos(theta))*K*K;

        return rot;
    }

    static double Norm_double(Eigen::Vector3d s1, Eigen::Vector3d s2){
        double result;
        result = sqrt((s2.x()-s1.x())*(s2.x()-s1.x()) + (s2.y()-s1.y())*(s2.y()-s1.y()) + (s2.z()-s1.z())*(s2.z()-s1.z()));

        return result;
    }

    static Eigen::Matrix3f normal2ROT(Eigen::Vector3f n){
        Eigen::Matrix3f rot;
        Eigen::Vector3f x, y, z, up;

        if(n(0) == 0 && n(1) == 0)
        {up << 0, 1, 0;}
        else
        {up << 0, 0, -1;}

        x = n;
        y = x.cross(up);
        z = x.cross(y);

        x = x/sqrt(x(0)*x(0) + x(1)*x(1) + x(2)*x(2));
        y = y/sqrt(y(0)*y(0) + y(1)*y(1) + y(2)*y(2));
        z = z/sqrt(z(0)*z(0) + z(1)*z(1) + z(2)*z(2));

        rot << x(0), y(0), z(0),
            x(1), y(1), z(1),
            x(2), y(2), z(2);

        return rot;
    }

    static Eigen::Vector3f proj(Eigen::Vector3f target_of_vec, Eigen::Vector3f proj_on_vec){
        /// (a dot b)
        /// --------- a
        ///  ||n||^2
        Eigen::Vector3f result_proj;
        float a_dot_b;
        a_dot_b = target_of_vec.dot(proj_on_vec);
        result_proj = (a_dot_b/target_of_vec.norm())*(target_of_vec);

        return result_proj;
    }


    static Eigen::Vector3f orientationERR(Eigen::Matrix3f Rdes, Eigen::Matrix3f R){
        Eigen::Matrix3f err_R = Rdes*R.transpose();
        float err_theta = (err_R.trace()-1.0)/2.0;

        if(err_theta >= 1.0) err_theta = 1 - 1e-6;
        else if(err_theta <= -1.0) err_theta = -1.0 + 1e-6;

        err_theta = acos(err_theta);

        Eigen::Vector3f err_vec;
        if(fabs(err_theta) < 1e-6){
            err_vec = Eigen::Vector3f::Zero();
        }
        else{
            err_vec(0) = 1.0/2.0/sin(err_theta)*(err_R(2,1) - err_R(1,2));
            err_vec(1) = 1.0/2.0/sin(err_theta)*(err_R(0,2) - err_R(2,0));
            err_vec(2) = 1.0/2.0/sin(err_theta)*(err_R(1,0) - err_R(0,1));
        }

        return err_theta*err_vec;
    }

    static Eigen::Matrix3f rotz2MAT(float rotz_rad){
        Eigen::Matrix3f Rz;
        Rz << cos(rotz_rad), -sin(rotz_rad), 0,
              sin(rotz_rad),cos(rotz_rad), 0,
                0,    0,       1;

        return Rz;
    }

    static Eigen::Matrix3f roty2MAT(float roty_rad){
        Eigen::Matrix3f Ry;
        Ry << cos(roty_rad), 0, sin(roty_rad),
                       0,    1,       0,
                    -sin(roty_rad), 0, cos(roty_rad);

        return Ry;
    }
    static Eigen::Matrix3f rotx2MAT(float rotx_rad){
        Eigen::Matrix3f Rx;
        Rx << 1,    0,                   0,
              0,    cos(rotx_rad),   -sin(rotx_rad),
              0,    sin(rotx_rad),   cos(rotx_rad);

        return Rx;
    }
    static float point2rad(float x, float y){ //convert 2d cartesian points to polar angles in range 0 ~ 2pi
       if(x > 0 && y >= 0) return (float)atan((double)y/(double)x);
       else if(x == 0 && y >= 0) return (float)M_PI/2.0;
       else if(x < 0 && y >= 0) return -fabs((float)atan((double)y/(double)x)) + (float)M_PI;
       else if(x < 0 && y < 0) return (float)atan((double)y/(double)x) + (float)M_PI;
       else if(x > 0 && y < 0) return -fabs((float)atan((double)y/(double)x)) + 2.0*(float)M_PI;
       else if(x == 0 && y < 0) return (float)M_PI*3.0/2.0;
       else if(x == 0 && y == 0) return (float)M_PI*3.0/2.0;
    }

    static Eigen::Vector3f global2local_point(float rotz_rad, Eigen::Vector3f _pCenter, Eigen::Vector3f _pGlobal){
        // Position(such as ZMP) calculation with respect to Robot Local frame ( Orgin : meddle of foot, Orientation : average of foot )

        // Foot average Orientation in global Frame
        // find "g_R_local" matrix---------------------------------------------------------------

        Eigen::Matrix3f g_R_local = rotz2MAT(rotz_rad);

        //--------------------------------------------------------------------------------------

        Eigen::Matrix3f local_R_g = g_R_local.inverse();

        Eigen::Vector3f pCenter2point_global = _pGlobal - _pCenter;

        Eigen::Vector3f pCenter2point_local = local_R_g*pCenter2point_global;

        pCenter2point_local.z() = _pGlobal.z();

        return pCenter2point_local;

    }

    static Eigen::Vector3f local2global_point(float rotz_rad, Eigen::Vector3f _pCenter, Eigen::Vector3f _pLocal){


        //// Calculate local point to global point
        // find "g_R_local" matrix---------------------------------------------------------------


        Eigen::Matrix3f g_R_local = rotz2MAT(rotz_rad);
        //--------------------------------------------------------------------------------------


        Eigen::Vector3f pCenter2plocal_global = g_R_local*(_pLocal);

        Eigen::Vector3f pGlobal_ = _pCenter + pCenter2plocal_global;

        pGlobal_.z() = _pLocal.z();

        return pGlobal_;

    }

/// "swap" needs to add "algorithm" library
//    // Function to get determinant of matrix
//    static int determinantOfMatrix(Eigen::Matrix3f mat, int n)
//    {
//        int num1, num2, det = 1, index,
//                        total = 1; // Initialize result

//        // temporary array for storing row
//        int temp[n + 1];

//        // loop for traversing the diagonal elements
//        for (int i = 0; i < n; i++)
//        {
//            index = i; // initialize the index

//            // finding the index which has non zero value
//            while (index < n && mat(index,i) == 0)
//            {
//                index++;
//            }
//            if (index == n) // if there is non zero element
//            {
//                // the determinant of matrix as zero
//                continue;
//            }
//            if (index != i)
//            {
//                // loop for swapping the diagonal element row and
//                // index row
//                for (int j = 0; j < n; j++)
//                {
//                    swap(mat(index,j), mat(i,j));
//                }
//                // determinant sign changes when we shift rows
//                // go through determinant properties
//                det = det * pow(-1, index - i);
//            }

//            // storing the values of diagonal row elements
//            for (int j = 0; j < n; j++)
//            {
//                temp[j] = mat(i,j);
//            }
//            // traversing every row below the diagonal element
//            for (int j = i + 1; j < n; j++)
//            {
//                num1 = temp[i]; // value of diagonal element
//                num2 = mat(j,i); // value of next row element

//                // traversing every column of row
//                // and multiplying to every row
//                for (int k = 0; k < n; k++)
//                {
//                    // multiplying to make the diagonal
//                    // element and next row element equal
//                    mat(j,k)
//                        = (num1 * mat(j,k)) - (num2 * temp[k]);
//                }
//                total = total * num1; // Det(kA)=kDet(A);
//            }
//        }

//        // multiplying the diagonal elements to get determinant
//        for (int i = 0; i < n; i++)
//        {
//            det = det * mat(i,i);
//        }
//        return (det / total); // Det(kA)/k=Det(A);
//    }

};

namespace Filter {
static float LPF(float input, float output, float f_cut, float ts) {
    float tau;
    float output_;
    if(f_cut != 0) {
        //        tau = 1/(2*PI*f_cut);
        //        output_ = (tau *  output + ts *input) / (tau + ts);
        tau = 1.0/(1.0 + 2*PI*f_cut*ts);
        output_ = tau*output + (1.0 - tau)*input;
    }
    else output_=0;
    return output_;
}

static Eigen::Vector3f LPF3d(Eigen::Vector3f input, Eigen::Vector3f output, float f_cut, float ts) {
    float tau;
    Eigen::Vector3f output_;
    if(f_cut != 0) {
        tau = 1/(2*PI*f_cut);
        for(int i=0; i<3; i++) {
            output_[i] = (tau *  output[i] + ts *input[i]) / (tau + ts);
        }
    }
    else output_ = Eigen::Vector3f::Zero();
    return output_;
}

static Eigen::Vector3f LPF3f(Eigen::Vector3f input, Eigen::Vector3f output, float f_cut, float ts) {
    float tau;
    Eigen::Vector3f output_;
    if(f_cut != 0) {
        tau = 1/(2*PI*f_cut);
        for(int i=0; i<3; i++) {
            output_[i] = (tau *  output[i] + ts *input[i]) / (tau + ts);
        }
    }
    else output_ = Eigen::Vector3f::Zero();
    return output_;
}

static float HPF(float input, float input_pre, float output, float f_cut, float ts) {
    float tau;
    float output_;
    if(f_cut != 0) {
        tau = 1/(2*PI*f_cut);
        output_ = tau/(tau+ts)*output + tau/(tau+ts)*(input-input_pre);
    }
    else output_=0;
    return output_;
}

static float Limit(float input, float low_limit, float upper_limit){
    float output_ = input;
    if(input >= upper_limit){
        output_ = upper_limit;
    }
    else if(input <= low_limit){
        output_ = low_limit;
    }

    return output_;
}
static Eigen::Vector3f Limit3f(Eigen::Vector3f input, Eigen::Vector3f low_limit, Eigen::Vector3f upper_limit){
    Eigen::Vector3f output_ = input;
    if(input.x() >= upper_limit.x()){
        output_.x() = upper_limit.x();
    }
    else if(input.x() <= low_limit.x()){
        output_.x() = low_limit.x();
    }

    if(input.y() >= upper_limit.y()){
        output_.y() = upper_limit.y();
    }
    else if(input.y() <= low_limit.y()){
        output_.y() = low_limit.y();
    }

    if(input.z() >= upper_limit.z()){
        output_.z() = upper_limit.z();
    }
    else if(input.z() <= low_limit.z()){
        output_.z() = low_limit.z();
    }

    return output_;
}

static float WindowFilter(float input, float output, float size){
    float output_ = output;
    float half_size = size/2.0;
    if(input >= output + half_size){
        output_ = input - half_size;
    }
    else if(input <= output - half_size){
        output_ = input + half_size;
    }
    else {
        output_ = output;
    }
    return output_;
}

static float DeadZone(float input, float low_clamp, float upper_clamp){
    //just clamping
    float output_;
    if(input > low_clamp && input < upper_clamp)
        output_ = 0.0;
    else
        output_ = input;
    return output_;

}

static float DeadZone2(float input, float low_clamp, float upper_clamp){
    // clamping and stick the both clamp
    float output_ = input;

    if(input <= low_clamp){
        output_ = input - low_clamp;
    }
    else if(low_clamp < input && input < upper_clamp){
        output_ = 0;
    }
    else if(input >= upper_clamp){
        output_ = input - upper_clamp;
    }

    return output_;
}

static float Max(float input1, float input2){
    if(input1 > input2) return input1;
    else if(input1 < input2) return input2;
    else return input1;
}

static float Min(float input1, float input2){
    if(input1 > input2) return input2;
    else if(input1 < input2) return input1;
    else return input1;
}

static float Max3(float input1, float input2, float input3){
    return Max(Max(input1,input2),input3);
}

static float Min3(float input1, float input2, float input3){
    return Min(Min(input1,input2),input3);
}

static float Max4(float input1, float input2, float input3, float input4){
    return Max(Max(Max(input1,input2),input3),input4);
}

}


#endif
