import { ImageResponse } from "next/og";

export const size = { width: 512, height: 512 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    <div style={{ alignItems: "center", background: "#0b0d0e", display: "flex", height: "100%", justifyContent: "center", width: "100%" }}>
      <div style={{ alignItems: "center", border: "10px solid #d4ad55", borderRadius: 84, display: "flex", height: 344, justifyContent: "center", width: 344 }}>
        <div style={{ color: "#f4f1e9", display: "flex", fontFamily: "sans-serif", fontSize: 230, fontWeight: 700, letterSpacing: 0, lineHeight: 1, marginTop: -18 }}>E</div>
      </div>
    </div>,
    size,
  );
}
