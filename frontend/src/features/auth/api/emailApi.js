import axiosInstance from "../../../lib/axios"; 

export const sendVerificationCode = async (email) => {
  const response = await axiosInstance.post(
    "/email/send-verification-code",
    { email },
  );
  return response.data;
};

export const verifyCode = async (email, code) => {
  const response = await axiosInstance.post("/email/verify-code", {
    email,
    code,
  });
  return response.data;
};
