import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Yembro — комбикорма для птицеводства",
    short_name: "Yembro",
    description: "Yembro — корма, по которым стадо растёт ровно. Бройлер, несушка, родительское стадо.",
    start_url: "/",
    display: "standalone",
    background_color: "#FBF7F0",
    theme_color: "#E0091F",
    icons: [
      { src: "/mark.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/mark.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/mark.png", sizes: "any", type: "image/png", purpose: "maskable" },
    ],
  };
}
