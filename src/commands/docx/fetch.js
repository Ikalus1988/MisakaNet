if (!response.ok) {
  throw new Error(`Failed to fetch document: ${response.statusText}`);
}

const data = await response.json();
return data.content;