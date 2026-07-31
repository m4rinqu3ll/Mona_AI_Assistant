import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Mona — Private AI Assistant",
    short_name: "Mona",
    description: "Private conversations and approvals with Mona.",
    start_url: "/",
    display: "standalone",
    background_color: "#0b1219",
    theme_color: "#101923",
  };
}
