export const handler = async (event) => {
  console.log("Lambda 1 - JS invoked with event: ", event);

  return {
    statusCode: 200,
  };
};
