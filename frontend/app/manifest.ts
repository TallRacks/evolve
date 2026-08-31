import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Evolve Artist Operations",
    short_name: "Evolve",
    description: "Private artist management and operations workspace.",
    start_url: "/dashboard",
    scope: "/",
    display: "standalone",
    background_color: "#0b0d0e",
    theme_color: "#0b0d0e",
    orientation: "portrait-primary",
    categories: ["business", "productivity"],
    icons: [
      { src: "/icon", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Dashboard", short_name: "Home", url: "/dashboard" },
      { name: "Calendar", short_name: "Calendar", url: "/workspace/calendar" },
      { name: "Tasks", short_name: "Tasks", url: "/workspace/tasks" },
      { name: "Notifications", short_name: "Inbox", url: "/workspace/notifications" },
    ],
  };
}
