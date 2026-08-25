import React, { useState, useEffect } from 'eact';

export const ConnectPage = () => {
  const [volume, setVolume] = useState<number>(() => {
    const saved = localStorage.getItem('voice-volume');
    return saved!== null? parseFloat(saved) : 0.5;
  });

  const handleVolumeChange = (newVolume: number) => {
    setVolume(newVolume);
    localStorage.setItem('voice-volume', newVolume.toString());
  };

  return (
    <div className="p-4">
      <h1 className="text-xl font-bold mb-4">Connect to MisakaNet</h1>
      <div className="flex flex-col gap-2">
        <label htmlFor="volume-slider" className="text-sm font-medium">
          Voice Volume: {Math.round(volume * 100)}%
        </label>
        <input
          id="volume-slider"
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={volume}
          onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
          className="w-full"
        />
      </div>
      {/* Rest of the connect page components */}
    </div>
  );
};