export const scrollSx = {
  overflow: "auto",
  scrollbarWidth: "thin",
  scrollbarColor: "#44506a #12151c",
  "&::-webkit-scrollbar": {
    width: 8,
    height: 8,
  },
  "&::-webkit-scrollbar-track": {
    background: "#12151c",
    borderRadius: 8,
  },
  "&::-webkit-scrollbar-thumb": {
    background: "#44506a",
    borderRadius: 8,
    border: "2px solid #12151c",
  },
  "&::-webkit-scrollbar-thumb:hover": {
    background: "#7c9cff",
  },
};

export const globalScrollbarStyles = {
  "*": {
    scrollbarWidth: "thin",
    scrollbarColor: "#44506a #12151c",
  },
  "*::-webkit-scrollbar": {
    width: 8,
    height: 8,
  },
  "*::-webkit-scrollbar-track": {
    background: "#12151c",
  },
  "*::-webkit-scrollbar-thumb": {
    background: "#44506a",
    borderRadius: 8,
    border: "2px solid #12151c",
  },
  "*::-webkit-scrollbar-thumb:hover": {
    background: "#7c9cff",
  },
};
