import '../styles/command-input.css';

function CommandInput({ value, onChange, placeholder }) {
  // Function to handle clearing input
  const handleClear = () => {
    onChange('');
  };

  console.log('CommandInput rendering with value:', value); // Add debug log

  return (
    <div className="input-wrapper">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="command-input"
        placeholder={placeholder}
        style={{ border: '1px solid #ccc' }} // Add border to visualize input box position
      />
      <button 
        className="clear-button"
        onClick={handleClear}
        aria-label="Clear input"
        style={{ border: '1px solid red' }} // Add border to visualize button position
      >
        ✕
      </button>
    </div>
  );
}

export default CommandInput; 