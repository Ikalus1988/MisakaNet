if (response.code === 1770002) {
    const fetchedContent = await fetchDocument(token, docId);
    if (fetchedContent.includes(content)) {
      console.log('Content was successfully written despite the error.');
      return;
    }
  }

  throw new Error(`Failed to update document: ${error.message}`);