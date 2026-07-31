import { Box, Skeleton, Stack } from "@mui/material";

export default function Loading() {
  return (
    <Stack aria-label="Loading page" spacing={2.25}>
      <Skeleton height={96} variant="rounded" />
      <Box
        sx={{
          display: "grid",
          gap: 2.25,
          gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", xl: "repeat(4, minmax(0, 1fr))" }
        }}
      >
        <Skeleton height={132} variant="rounded" />
        <Skeleton height={132} variant="rounded" />
        <Skeleton height={132} variant="rounded" />
        <Skeleton height={132} variant="rounded" />
      </Box>
      <Skeleton height={260} variant="rounded" />
    </Stack>
  );
}
