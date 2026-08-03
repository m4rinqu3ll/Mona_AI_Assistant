import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "MoMo — Private AI Assistant",
    short_name: "MoMo",
    description: "Private conversations and approvals with MoMo.",
    start_url: "/",
    display: "standalone",
    background_color: "#0b1219",
    theme_color: "#101923",
  };
}
